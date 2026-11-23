#!/usr/bin/env python3
"""Login por telnet en RouterOS y ejecucion de comandos.

    python tools/rostelnet.py --host 192.168.1.2 --user admin
    python tools/rostelnet.py --host 192.168.1.2 --user admin --cmd "/system/resource/print"

Sin --password se manda contraseña vacia (primer arranque). La negociacion
telnet se responde con WONT/DONT para que el servidor no se quede esperando.
"""

import argparse
import socket
import sys
import time

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def limpiar_iac(buf, sock):
    """Quita la negociacion telnet y responde a las opciones."""
    out = bytearray()
    i = 0
    while i < len(buf):
        b = buf[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= len(buf):
            break
        cmd = buf[i + 1]
        if cmd in (DO, DONT, WILL, WONT):
            if i + 2 >= len(buf):
                break
            opt = buf[i + 2]
            if cmd == DO:
                sock.sendall(bytes([IAC, WONT, opt]))
            elif cmd == WILL:
                sock.sendall(bytes([IAC, DONT, opt]))
            i += 3
        elif cmd == SB:
            j = buf.find(bytes([IAC, SE]), i + 2)
            if j < 0:
                break
            i = j + 2
        else:
            i += 2
    return bytes(out)


class Telnet:
    def __init__(self, host, port=23, timeout=6.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(0.5)
        self.buf = b""

    def leer(self, segundos=2.0):
        t0 = time.time()
        out = b""
        while time.time() - t0 < segundos:
            try:
                d = self.s.recv(4096)
            except socket.timeout:
                continue
            if not d:
                break
            out += limpiar_iac(d, self.s)
        self.buf += out
        return out

    def esperar(self, needle, segundos=8.0):
        t0 = time.time()
        while time.time() - t0 < segundos:
            if needle.lower() in self.buf.lower():
                return True
            self.leer(0.5)
        return False

    def enviar(self, texto):
        self.s.sendall(texto.encode() + b"\r\n")
        self.buf = b""
        return self.leer(1.2)

    def cerrar(self):
        try:
            self.s.close()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="192.168.1.2")
    ap.add_argument("--puerto", type=int, default=23)
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="")
    ap.add_argument("--nueva", help="contraseña nueva a fijar si el login entra")
    ap.add_argument("--cmd", action="append", default=[],
                    help="comando RouterOS a ejecutar (repetible)")
    args = ap.parse_args()

    t = Telnet(args.host, args.puerto)
    try:
        if not t.esperar(b"Login:", 10):
            print("[!] no aparece el prompt de login")
            print(t.buf.decode("utf-8", "replace"))
            return 2
        print("[ok] prompt de login")
        print(t.enviar(args.user).decode("utf-8", "replace"))
        if not t.esperar(b"Password:", 5):
            print("[!] no pide contraseña; salida:")
            print(t.buf.decode("utf-8", "replace"))
            return 2
        out = t.enviar(args.password)
        print(out.decode("utf-8", "replace"))
        time.sleep(0.5)
        print(t.leer(2.0).decode("utf-8", "replace"))

        if b"[admin@" in t.buf or b"> " in t.buf:
            print("[ok] sesion iniciada")
            if args.nueva:
                for cmd in (f'/user/set admin password="{args.nueva}"',
                            "/system/note/set note=\"port ED500\""):
                    out = t.enviar(cmd)
                    print(out.decode("utf-8", "replace"))
            for cmd in args.cmd:
                print(">>>", cmd)
                print(t.enviar(cmd).decode("utf-8", "replace"))
            return 0
        print("[!] login no confirmado")
        return 1
    finally:
        t.cerrar()


if __name__ == "__main__":
    sys.exit(main())
