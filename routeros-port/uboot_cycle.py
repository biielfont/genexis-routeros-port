#!/usr/bin/env python3
"""Reinicia el ED500 por software y lo devuelve a nuestro kernel, sin tocar la corriente.

U-Boot tiene el comando `reset`, que reinicia el SoC entero: estando en su
prompt no hace falta cortar la alimentacion. El unico detalle es que tras el
reset U-Boot autoarranca el firmware de la NAND en 3 s, asi que hay que
machacar CR para quedarse en el prompt. Eso es lo que hace este script.

    python uboot_cycle.py status           # donde esta la placa ahora
    python uboot_cycle.py reset            # reinicia y se queda en U-Boot
    python uboot_cycle.py boot             # carga uImage-563 y bootm
    python uboot_cycle.py cycle            # reset + catch + TFTP + bootm (lo normal)
    python uboot_cycle.py watch --horas 6  # ademas rearma si la placa se reinicia
    python uboot_cycle.py poke            # despertar una consola muerta y arrancar
    python uboot_cycle.py cmd "printenv"   # un comando suelto al prompt actual

Desde Linux se escribe directamente RCU_RST_REQ por /dev/mem: 0x16000010, bit
30 (0x40000000). Es el mismo bit que pide el nodo `syscon-reboot` del DTS
(presente en /proc/device-tree/rcu@16000000/reboot), pero no depende de que el
kernel lo haya registrado ni de que el shell tenga el applet `reboot`: en el
chroot de RouterOS `reboot` no esta en el PATH, y si el handler fallara el
kernel se queda en "Reboot failed -- System halted", que en remoto es fatal.

Todo va a RAM: no se escribe NAND.
"""

import argparse
import os
import re
import socket
import sys
import time

import serial
import tftplib

PORT = os.environ.get("ED500_PORT", "COM4")
IMG = "uImage-563"
DIR_IMG = "out"
LOG = "logs/uboot_cycle.log"
UBOOT = b"grx500 #"
LINUX = b"~ #"
ADDR = "0x80500000"

# RCU del GRX350 (0x16000000) + offset 0x10 de RCU_RST_REQ, bit 30 = reset global
REG_RESET = "0x16000010"
BIT_RESET = 0x40000000


def ip_hacia(destino, por_defecto="192.168.1.161"):
    """IP local que el sistema usaria para llegar a `destino` (no manda nada)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((destino, 80))
        return s.getsockname()[0]
    except OSError:
        return por_defecto
    finally:
        s.close()


class Consola:
    def __init__(self, puerto=PORT, log=LOG):
        os.makedirs(os.path.dirname(log) or ".", exist_ok=True)
        self.s = serial.Serial(puerto, 115200, timeout=0.02)
        self.log = open(log, "ab")
        self.log.write(f"\n\n### {time.strftime('%Y-%m-%d %H:%M:%S')} "
                       f"{' '.join(sys.argv[1:])} ###\n".encode())
        self.log.flush()
        time.sleep(0.2)

    def w(self, data):
        self.log.write(data)
        self.log.flush()

    def wr(self, texto):
        self.s.write(texto.encode() + b"\r")
        self.s.flush()

    def rd(self, segundos):
        t0, out = time.time(), b""
        while time.time() - t0 < segundos:
            d = self.s.read(4096)
            if d:
                out += d
                self.w(d)
        return out

    def rd_hasta(self, needles, segundos):
        """Lee hasta que aparezca cualquiera de `needles` (bytes) o venza el plazo."""
        if isinstance(needles, bytes):
            needles = (needles,)
        t0, out = time.time(), b""
        while time.time() - t0 < segundos:
            d = self.s.read(4096)
            if d:
                out += d
                self.w(d)
                if any(n in out for n in needles):
                    break
        return out

    def estado(self):
        """Devuelve 'uboot', 'linux' o 'desconocido', y lo ultimo leido."""
        out = self.rd(0.6)
        self.s.write(b"\r")
        out += self.rd(2.0)
        if UBOOT in out:
            return "uboot", out
        if LINUX in out:
            return "linux", out
        return "desconocido", out

    def cazar(self, segundos):
        """Machaca CR hasta ver el prompt de U-Boot."""
        buf = b""
        t0 = time.time()
        while time.time() - t0 < segundos:
            self.s.write(b"\r")
            buf += self.rd(0.03)
            if UBOOT in buf:
                return True
            if len(buf) > 400000:
                buf = buf[-100000:]
        return False

    def reset_por_rcu(self):
        """Reset del SoC escribiendo RCU_RST_REQ por /dev/mem.

        Lee el registro, le hace OR del bit 30 y lo escribe: no borra los
        otros bits de reset que esten latcheados. No pasa por el kernel, asi
        que funciona aunque no haya restart handler (el caso actual).
        """
        for binario in ("busybox devmem", "devmem"):
            # el marcador evita confundir el valor con la direccion que el
            # propio shell devuelve al hacer eco del comando
            self.wr(f"V=$({binario} {REG_RESET}); echo \"RCU=$V\"")
            out = self.rd(1.5)
            m = re.search(rb"RCU=0x([0-9a-fA-F]{1,8})", out)
            if not m:
                continue
            valor = int(m.group(1), 16)
            print(f"[reset] RCU_RST_REQ={valor:#010x} -> "
                  f"{valor | BIT_RESET:#010x}", flush=True)
            self.wr(f"{binario} {REG_RESET} 32 "
                    f"0x{valor | BIT_RESET:08x}")
            self.rd(0.4)
            return True
        return False

    def reiniciar(self, segundos=150):
        """Deja la placa en el prompt de U-Boot, venga de donde venga."""
        est, out = self.estado()
        print(f"[estado] {est}", flush=True)

        if est == "linux":
            # El RCU escribe el mismo bit que syscon-reboot, sin depender de
            # que el kernel tenga el handler registrado. Si no hay /dev/mem,
            # se intenta el applet de busybox (el `reboot` suelto no existe
            # en el PATH del chroot de RouterOS).
            print("[reset] reset por RCU desde Linux", flush=True)
            if not self.reset_por_rcu():
                print("[!] sin acceso a /dev/mem: pruebo busybox reboot -f",
                      flush=True)
                self.wr("busybox reboot -f")
                self.rd(1.0)
                self.wr("reboot -f")
            # el SoC tarda menos de un segundo; se espera un poco por si acaso
            self.rd_hasta((b"ROM VER", b"U-Boot", b"Hit any key"), 5)
        elif est == "uboot":
            print("[reset] reset en U-Boot", flush=True)
            self.wr("reset")
            self.rd(1.0)
        else:
            # puede estar arrancando: el martilleo de CR sirve igual
            print("[reset] estado desconocido: martilleo CR por si esta en autoboot",
                  flush=True)

        if not self.cazar(segundos):
            print("[!] no he cazado el prompt de U-Boot", flush=True)
            return False
        print("[ok] prompt de U-Boot cazado", flush=True)
        return True

    def arrancar(self, img=IMG, addr=ADDR, pc_ip=None, puerto_tftp=None,
                 veredicto=True):
        """Asume que ya estamos en el prompt de U-Boot."""
        pc_ip = pc_ip or ip_hacia("192.168.1.1")
        tam = os.path.getsize(os.path.join(DIR_IMG, img))

        for cmd in ("setenv ipaddr 192.168.1.1", f"setenv serverip {pc_ip}"):
            self.wr(cmd)
            self.rd_hasta((UBOOT, b"## Error"), 3)

        puertos = [puerto_tftp] if puerto_tftp else [69]
        if 6969 not in puertos:
            puertos.append(6969)

        out = b""
        for p in puertos:
            self.wr(f"setenv tftpdstp {p}")
            self.rd_hasta((UBOOT, b"## Error"), 3)
            print(f"[tftp] tftpboot {addr} {img} (puerto {p})", flush=True)
            self.wr(f"tftpboot {addr} {img}")
            out = self.rd_hasta((b"Bytes transferred", b"## Error",
                                 b"TFTP error", b"Retry count exceeded"), 90)
            if b"Bytes transferred" in out:
                break
            print(f"[!] sin transferencia en el puerto {p}", flush=True)

        if b"Bytes transferred" not in out:
            print("[!] TFTP no confirmo la transferencia; no arranco", flush=True)
            return b""

        try:
            linea = [l for l in out.split(b"\n") if b"Bytes transferred" in l][-1]
            n = int(linea.split(b"= ")[1].split(b" ")[0])
        except Exception:  # noqa: BLE001
            n = -1
        if n not in (-1, tam):
            print(f"[!] AVISO: transferidos {n} bytes, el fichero tiene {tam}",
                  flush=True)
        else:
            print(f"[ok] transferidos {n} bytes (coincide)", flush=True)

        print("[boot] bootm", flush=True)
        self.wr(f"bootm {addr}")
        # se corta en cuanto hay shell (o fallo), no se queda mirando 5 minutos
        salida = self.rd_hasta((b"~ #", b"[admin@", b"Login:", b"Kernel panic",
                                b"Reboot failed", b"Attempted to kill init"), 240)
        if veredicto:
            print(f"[veredicto] {self.veredicto(salida)}", flush=True)
        return salida

    @staticmethod
    def veredicto(salida):
        if b"Linux version 5.6.3" not in salida:
            if b"Kernel panic" in salida or b"Oops" in salida:
                return "PANIC/OOPS antes del banner"
            return "el kernel no ha llegado a imprimir su version"
        if b"Kernel panic" in salida:
            return "arranco e hizo PANIC"
        partes = ["arranco"]
        for clave, txt in ((b"gswip", "switch"), (b"lan1", "lan1"),
                           (b"red: ", "red"), (b"web: http", "http")):
            if clave in salida:
                partes.append(txt)
        if b"~ #" in salida:
            partes.append("shell")
        if b"[admin@" in salida or b"Login:" in salida:
            partes.append("cli mikrotik")
        return " + ".join(partes)

    def seguir(self, horas, img=IMG, addr=ADDR, pc_ip=None, puerto_tftp=None):
        """Vigila la consola y rearma el arranque si la placa vuelve a U-Boot."""
        limite = time.time() + horas * 3600
        buf = b""
        avisado = False
        while time.time() < limite:
            d = self.rd(1.0)
            if not d:
                continue
            buf = (buf + d)[-400:]
            if UBOOT in buf and not avisado:
                avisado = True
                print("[watch] la placa esta en U-Boot: rearmo el arranque",
                      flush=True)
                self.arrancar(img, addr, pc_ip, puerto_tftp)
                buf = b""
                avisado = False
        return True

    def close(self):
        self.s.close()
        self.log.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("status", help="decir donde esta la placa")
    sub.add_parser("reset", help="reiniciar y quedarse en U-Boot")

    for nombre, ayuda in (("boot", "cargar la imagen y arrancar"),
                          ("cycle", "reset + catch + cargar + arrancar")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--img", default=IMG)
        p.add_argument("--addr", default=ADDR)
        p.add_argument("--ip", help="IP del PC (por defecto se detecta sola)")
        p.add_argument("--segundos", type=int, default=150,
                       help="ventana para cazar U-Boot")

    p = sub.add_parser("watch", help="ciclo y luego rearmar si se reinicia")
    p.add_argument("--horas", type=float, default=6.0)
    p.add_argument("--img", default=IMG)
    p.add_argument("--addr", default=ADDR)
    p.add_argument("--ip")
    p.add_argument("--segundos", type=int, default=150)

    p = sub.add_parser("poke", help="consola muerta: senales, catch y arranque")
    p.add_argument("--img", default=IMG)
    p.add_argument("--addr", default=ADDR)
    p.add_argument("--ip")
    p.add_argument("--segundos", type=int, default=180)

    p = sub.add_parser("cmd", help="mandar un comando al prompt actual")
    p.add_argument("texto")

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 1

    c = Consola()
    try:
        if args.cmd == "status":
            est, out = c.estado()
            print(f"estado: {est}")
            cola = out.decode("utf-8", "replace").replace("\r", "")
            print(cola[-1200:])
            return 0

        if args.cmd == "cmd":
            c.wr(args.texto)
            print(c.rd(5.0).decode("utf-8", "replace").replace("\r", ""))
            return 0

        if args.cmd == "reset":
            return 0 if c.reiniciar() else 2

        if args.cmd == "boot":
            est, _ = c.estado()
            if est != "uboot":
                print(f"[!] la placa esta en '{est}', no en U-Boot: usa cycle",
                      flush=True)
                return 2
            c.arrancar(args.img, args.addr, args.ip)
            return 0

        if args.cmd == "cycle":
            pc_ip = args.ip or ip_hacia("192.168.1.1")
            print(f"[tftp] sirviendo {os.path.abspath(DIR_IMG)} a {pc_ip}",
                  flush=True)
            puerto = tftplib.start(DIR_IMG, out=lambda t: print(f"[tftp] {t}",
                                                               flush=True))
            if puerto is None:
                print("[!] no hay puerto TFTP libre", flush=True)
                return 2
            if not c.reiniciar(segundos=args.segundos):
                return 2
            c.arrancar(args.img, args.addr, pc_ip, puerto)
            return 0

        if args.cmd == "poke":
            # Consola sin shell: se mandan señales al proceso en primer plano
            # (Ctrl+C, Ctrl+\, Ctrl+Z) y un BREAK. Si sysinit muere, el kernel
            # hace panic y, con panic=20, reinicia; el martilleo de CR caza
            # U-Boot y se recarga la imagen.
            pc_ip = args.ip or ip_hacia("192.168.1.1")
            puerto = tftplib.start(DIR_IMG, out=lambda t: print(f"[tftp] {t}",
                                                               flush=True))
            if puerto is None:
                print("[!] no hay puerto TFTP libre", flush=True)
                return 2
            print("[poke] Ctrl+C, Ctrl+\\, Ctrl+Z y BREAK", flush=True)
            for seq in (b"\x03\x03\x03", b"\x1c", b"\x1a", b"\x03\x03"):
                c.s.write(seq)
                c.s.flush()
                time.sleep(0.4)
            try:
                c.s.send_break(0.3)
            except Exception:  # noqa: BLE001
                pass
            if not c.cazar(args.segundos):
                print("[!] no ha aparecido U-Boot; la placa sigue sin consola",
                      flush=True)
                return 2
            c.arrancar(args.img, args.addr, pc_ip, puerto)
            return 0

        if args.cmd == "watch":
            pc_ip = args.ip or ip_hacia("192.168.1.1")
            puerto = tftplib.start(DIR_IMG, out=lambda t: print(f"[tftp] {t}",
                                                               flush=True))
            if puerto is None:
                print("[!] no hay puerto TFTP libre", flush=True)
                return 2
            est, _ = c.estado()
            if est != "uboot":
                c.reiniciar(segundos=args.segundos)
            c.arrancar(args.img, args.addr, pc_ip, puerto)
            print(f"[watch] vigilando {args.horas} h (Ctrl+C para parar)",
                  flush=True)
            c.seguir(args.horas, args.img, args.addr, pc_ip, puerto)
            return 0
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
