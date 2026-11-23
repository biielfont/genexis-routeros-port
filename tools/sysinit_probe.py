#!/usr/bin/env python3
"""Lanza `/sbin/sysinit start` desde el shell del chroot, con red de seguridad.

Un solo proceso hace de piloto y de cazador: manda el comando, lee la consola
y, si en cualquier momento aparece el prompt de U-Boot (la placa se ha
reiniciado), sirve `out/uImage-563` por TFTP y la arranca otra vez. Todo va a
RAM; la NAND solo se lee.

El comando deja la salida de sysinit y su backtrace en `/flash/rw`, asi que
aunque la consola se llene se puede leer despues. Antes de lanzar nada copia
`/nova/bin/loader` a `/flash/rw/loader.bak`.

    python tools/sysinit_probe.py                 # 120 s de ventana
    python tools/sysinit_probe.py --segundos 180
    python tools/sysinit_probe.py --solo-echo    # no lanza sysinit

Si la placa se reinicia y el cazador no llega a U-Boot, el LED de la placa
queda en el firmware de la NAND: en ese caso hay que cortar la corriente.
Por eso el proceso se queda pegado a la consola hasta el final.
"""

import argparse
import os
import sys
import time

# el script vive en tools/; tftplib y catch_final estan en la raiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial  # noqa: E402
import tftplib  # noqa: E402
from catch_final import ip_hacia  # noqa: E402

PORT = os.environ.get("ED500_PORT", "COM4")
LOG = "logs/sysinit_probe.log"
IMG = "uImage-563"
DIR_IMG = "out"
ADDR = "0x80500000"
UBOOT = b"grx500 #"

# El `&` deja sysinit en segundo plano y el shell sigue siendo nuestro. La
# salida va a un fichero de /flash/rw (tmpfs), no a la consola.
CMD_SYSINIT = (
    "echo ===PRE===; /bin/busybox ps | /bin/busybox head -n 20; "
    "/bin/busybox cp -f /nova/bin/loader /flash/rw/loader.bak; "
    "echo BACKUP=$?; "
    "/sbin/sysinit start </dev/null >/flash/rw/sysinit_probe.out 2>&1 & "
    "echo STARTED=$!; /bin/busybox sleep 25; "
    "echo ===TAIL===; /bin/busybox tail -n 50 /flash/rw/sysinit_probe.out; "
    "echo ===BT===; /bin/busybox tail -n 80 /flash/rw/logs/backtrace.log 2>&1; "
    "echo ===PS===; /bin/busybox ps | /bin/busybox head -n 30; "
    "echo ===RW===; /bin/busybox ls -l /flash/rw; "
    "echo ===END==="
)
CMD_SOLO = (
    "echo ===PRE===; /bin/busybox ps | /bin/busybox head -n 20; "
    "echo ===TAIL===; /bin/busybox tail -n 30 /flash/rw/sysinit_probe.out 2>&1; "
    "echo ===BT===; /bin/busybox tail -n 60 /flash/rw/logs/backtrace.log 2>&1; "
    "echo ===PS===; /bin/busybox ps | /bin/busybox head -n 30; "
    "echo ===END==="
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segundos", type=int, default=120,
                    help="ventana de lectura tras lanzar el comando")
    ap.add_argument("--solo-echo", action="store_true",
                    help="no lanza sysinit: solo ensena el estado de /flash/rw")
    args = ap.parse_args()

    os.makedirs("logs", exist_ok=True)
    log = open(LOG, "ab")
    log.write(f"\n\n### {time.strftime('%Y-%m-%d %H:%M:%S')} "
              f"{' '.join(sys.argv[1:])} ###\n".encode())
    log.flush()

    def w(b):
        log.write(b)
        log.flush()

    def say(t):
        print(t, flush=True)

    pc_ip = ip_hacia("192.168.1.1")
    say(f"consola {PORT}; TFTP de rescate en {pc_ip}")
    puerto = tftplib.start(DIR_IMG, out=say)

    s = serial.Serial(PORT, 115200, timeout=0.03)
    try:
        # vaciar lo que quede pendiente
        t0 = time.time()
        while time.time() - t0 < 0.8:
            d = s.read(4096)
            if d:
                w(d)
        s.write(b"\r")
        out = _leer(s, w, 1.5)
        if b"~ #" not in out:
            say("AVISO: no veo el prompt '~ #'; sigo de todas formas")

        cmd = CMD_SOLO if args.solo_echo else CMD_SYSINIT
        say("mandando el comando")
        s.write(cmd.encode() + b"\r")

        limite = time.time() + args.segundos
        buf = b""
        recuperado = False
        while time.time() < limite:
            d = s.read(4096)
            if not d:
                continue
            w(d)
            buf += d
            if UBOOT in buf:
                say("U-Boot en la consola: la placa se ha reiniciado, recupero")
                recuperado = _recuperar(s, w, say, puerto, pc_ip)
                break
            if b"===END===" in buf:
                say("fin del comando")
                break
        if not recuperado and b"===END===" not in buf:
            say("sin marca de fin: la consola no ha terminado el comando")
        say(f"consola completa en {LOG}")
        return 0 if (recuperado or b"===END===" in buf) else 2
    finally:
        s.close()
        log.close()


def _leer(s, w, segundos, hasta=None):
    t0, out = time.time(), b""
    while time.time() - t0 < segundos:
        d = s.read(4096)
        if d:
            out += d
            w(d)
            if hasta and hasta in out:
                break
    return out


def _recuperar(s, w, say, puerto, pc_ip):
    """Asume que U-Boot esta arrancando: machaca CR, carga por TFTP y bootm."""
    # el banner puede haber salido con la cuenta atras ya empezada
    for _ in range(40):
        s.write(b"\r")
        if UBOOT in _leer(s, w, 0.1):
            break
    say("prompt de U-Boot cazado; cargo la imagen")
    s.write(b"setenv ipaddr 192.168.1.1\r")
    _leer(s, w, 1.0, UBOOT)
    s.write(b"setenv serverip " + pc_ip.encode() + b"\r")
    _leer(s, w, 1.0, UBOOT)

    puertos = [puerto] if puerto else []
    for p in (69, 6969):
        if p not in puertos:
            puertos.append(p)
    out = b""
    for p in puertos:
        s.write(b"setenv tftpdstp " + str(p).encode() + b"\r")
        _leer(s, w, 1.0, UBOOT)
        say(f"tftpboot (puerto {p})")
        s.write(b"tftpboot " + ADDR.encode() + b" " + IMG.encode() + b"\r")
        out = _leer(s, w, 120, b"Bytes transferred")
        if b"Bytes transferred" in out:
            break
    if b"Bytes transferred" not in out:
        say("TFTP no confirmo la transferencia; la placa sigue en U-Boot")
        return False
    say("transferencia OK; bootm")
    s.write(b"bootm " + ADDR.encode() + b"\r")
    out = _leer(s, w, 240, b"~ #")
    if b"~ #" in out:
        say("recuperada: shell otra vez")
        return True
    say("bootm sin shell; revisa la consola")
    return False


if __name__ == "__main__":
    sys.exit(main())
