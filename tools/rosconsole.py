#!/usr/bin/env python3
"""Login y comandos por la consola serie de RouterOS.

El login de consola de RouterOS lee byte a byte: si se manda "admin\\r" de
golpe, el servicio de consola se queda con el resto de la rafaga. Este script
escribe cada byte con una pausa pequena para que el login lo reciba entero.

    python tools/rosconsole.py --cmd "/system resource print"
    python tools/rosconsole.py --nueva "otra-clave" --cmd "/user print"
    python tools/rosconsole.py --script config.rsc

La contrasena por defecto es la que pone /flash/autorun.scr (ed500). Si la
placa aun tiene admin sin contrasena, se reintenta con vacia. Si RouterOS pide
cambiar la contrasena en el primer login, se usa --nueva (o la actual).

Necesita COM4 libre: el cazador TFTP la libera 45 s despues de bootm.
"""

import argparse
import os
import re
import sys
import time

import serial

PORT = os.environ.get("ED500_PORT", "COM4")
LOG = "logs/rosconsole.log"
PROMPT = re.compile(rb"\[[^\]\r\n]{1,64}\]\s*>\s*$")


class RosConsole:
    def __init__(self, puerto=PORT, baudios=115200):
        os.makedirs(os.path.dirname(LOG) or ".", exist_ok=True)
        self.s = serial.Serial(puerto, baudios, timeout=0.05)
        self.log = open(LOG, "ab")
        self.buf = b""
        self.log.write(f"\n\n### {time.strftime('%Y-%m-%d %H:%M:%S')} "
                       f"{' '.join(sys.argv[1:])} ###\n".encode())
        self.log.flush()
        time.sleep(0.3)
        self.s.reset_input_buffer()

    def _w(self, data):
        self.log.write(data)
        self.log.flush()

    def read(self, segundos):
        t0, out = time.time(), b""
        while time.time() - t0 < segundos:
            d = self.s.read(4096)
            if d:
                out += d
                self._w(d)
        self.buf += out
        return out

    def wait(self, needles, segundos):
        if isinstance(needles, (bytes, bytearray)):
            needles = (needles,)
        t0 = time.time()
        while time.time() - t0 < segundos:
            if any(n.lower() in self.buf.lower() for n in needles):
                return True
            self.read(0.2)
        return False

    def write_slow(self, texto, pausa=0.04):
        """Escribe byte a byte; el login de RouterOS no usa FIFO."""
        for b in texto.encode() + b"\r":
            self.s.write(bytes([b]))
            self.s.flush()
            time.sleep(pausa)
        self.read(0.3)

    def limpiar(self, texto):
        texto = texto.replace(b"\r", b"")
        texto = re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]", b"", texto)
        return texto.decode("utf-8", "replace")

    def login(self, user, password, nueva=None):
        self.buf = b""
        self.s.write(b"\r")
        self.read(0.5)
        if not self.wait((b"Login:", b"login:"), 25):
            print("[!] no aparece MikroTik Login:")
            print(self.limpiar(self.buf[-1200:]))
            return False
        print("[ok] prompt de login")

        intentos = [password]
        if password != "":
            intentos.append("")
        for i, clave in enumerate(intentos):
            if i:
                # tras un fallo RouterOS vuelve a "Login:": hay que
                # reenviar el usuario, no solo la contrasena.
                print("[i] reintento con contrasena vacia")
                self.buf = b""
                if not self.wait((b"Login:", b"login:"), 8):
                    print("[!] no vuelve el prompt de login")
                    return False
            self.write_slow(user)
            self.buf = b""
            if not self.wait((b"Password:", b"password:"), 8):
                print("[!] no pide contrasena; salida:")
                print(self.limpiar(self.buf[-1200:]))
                return False
            self.write_slow(clave)
            self.read(2.0)
            bajo = self.buf.lower()
            if (b"new password" in bajo) or (b"repeat new password" in bajo):
                return self._cambiar(nueva or password or "ed500")
            if (b"login:" in bajo[-400:]) or (b"invalid" in bajo):
                continue
            if self.wait((b"] >", b"> "), 8):
                print("[ok] sesion iniciada")
                self.buf = b""
                return True
            # un segundo de margen por si el banner tarda
            self.read(2.0)
            if self.wait((b"] >", b"> "), 2):
                print("[ok] sesion iniciada")
                self.buf = b""
                return True
        print("[!] login no confirmado")
        print(self.limpiar(self.buf[-1200:]))
        return False

    def _cambiar(self, nueva):
        print("[i] RouterOS pide cambiar la contrasena")
        self.write_slow(nueva)
        if not self.wait((b"repeat", b"Repeat"), 8):
            print("[!] no aparece 'repeat new password>'")
            return False
        self.write_slow(nueva)
        if self.wait((b"] >", b"> "), 10):
            print("[ok] contrasena cambiada")
            return True
        print("[!] no se confirmo el cambio de contrasena")
        return False

    def cmd(self, texto, segundos=8.0):
        self.buf = b""
        print(f"\n>>> {texto}")
        self.write_slow(texto, 0.012)
        t0 = time.time()
        while time.time() - t0 < segundos:
            self.read(0.4)
            if PROMPT.search(self.buf.replace(b"\r", b"")):
                break
        salida = self.limpiar(self.buf)
        # quitar el eco del comando y las lineas vacias del final
        lineas = [l for l in salida.splitlines() if l.strip()]
        if lineas and texto.strip() in lineas[0]:
            lineas = lineas[1:]
        print("\n".join(lineas[-80:]))
        return "\n".join(lineas)

    def cerrar(self):
        try:
            self.s.close()
        finally:
            self.log.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=PORT)
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="ed500",
                    help="contrasena actual (por defecto la de autorun.scr)")
    ap.add_argument("--nueva", help="contrasena a fijar si RouterOS la pide")
    ap.add_argument("--cmd", action="append", default=[],
                    help="comando RouterOS (repetible)")
    ap.add_argument("--script", help="fichero .rsc con comandos, uno por linea")
    ap.add_argument("--segundos", type=float, default=10.0,
                    help="espera maxima por comando")
    args = ap.parse_args()

    comandos = list(args.cmd)
    if args.script:
        with open(args.script, encoding="utf-8") as f:
            comandos += [l.rstrip("\n") for l in f
                         if l.strip() and not l.lstrip().startswith("#")]

    c = RosConsole(args.port)
    try:
        if not c.login(args.user, args.password, args.nueva):
            return 2
        if args.nueva and "/user set" not in " ".join(comandos):
            comandos.insert(0, f'/user set admin password="{args.nueva}"')
        for cmd in comandos:
            c.cmd(cmd, args.segundos)
        if not comandos:
            print("\n[ok] consola autenticada; no habia comandos que ejecutar")
        return 0
    finally:
        c.cerrar()


if __name__ == "__main__":
    sys.exit(main())
