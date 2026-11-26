"""Hace bootm con lo que ya esta cargado en RAM y sigue la sesion.

Para cuando la imagen ya se transfirio (U-Boot esta en el prompt con
0x80500000 cargado) y no hace falta otro ciclo de corriente.
"""
import os
import sys
import time

import serial

PUERTO = "COM4"
BAUD = 115200
LOG = "logs/try563_v2.log"
SESION = "logs/mikrotik-session.txt"


def main():
    os.makedirs("logs", exist_ok=True)
    s = serial.Serial(PUERTO, BAUD, timeout=0.3)
    log = open(LOG, "ab")
    ses = open(SESION, "wb")
    t0 = time.time()

    def leer(seg, dest=None):
        o = b""
        fin = time.time() + seg
        while time.time() < fin:
            d = s.read(4096)
            if d:
                o += d
                log.write(d)
                log.flush()
                if dest is not None:
                    dest.write(d)
                    dest.flush()
        return o

    def enviar(txt, pausa=0.07):
        for c in txt.encode():
            s.write(bytes([c]))
            time.sleep(pausa)

    def esperar(pals, seg):
        o = b""
        fin = time.time() + seg
        while time.time() < fin:
            o += leer(0.3, ses)
            if any(p in o.lower() for p in pals):
                return o
        return o

    print("[i] drenando lo que quede en el buffer...")
    leer(1.5)
    print("[i] bootm 0x80500000")
    enviar("bootm 0x80500000\r")

    print("[i] esperando 'Login:' (60 s)")
    o = esperar([b"login:"], 60)
    print("[i] prompt:", "SI" if b"login:" in o.lower() else "NO")

    for clave, et in (("ed500", "ed500"), ("", "vacia")):
        print(f"[i] probando {et}")
        enviar("admin\r")
        o = esperar([b"assword"], 10)
        if b"assword" not in o.lower():
            print(f"[{et}] no pide contrasena")
            break
        enviar(clave + "\r")
        r = leer(40, ses)
        txt = r.decode("utf-8", "replace")
        print(f"[{et}] -> {txt.strip()[-200:]!r}")
        if "] >" in txt or "\n> " in txt:
            print(f"[{et}] SESION ABIERTA")
            for cmd in ("/system license print", "/system resource print",
                        "/interface print"):
                enviar(cmd + "\r")
                print(f"--- {cmd} ---")
                print(leer(12, ses).decode("utf-8", "replace"))
            break

    # H41 vuelca a up=150 s; seguir leyendo hasta pasar ese punto.
    print("[i] leyendo hasta el volcado H41 (up 150 s)")
    while time.time() - t0 < 240:
        leer(2, ses)
    s.close()
    log.close()
    ses.close()
    print("[i] fin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
