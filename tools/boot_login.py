#!/usr/bin/env python3
"""Arranca por TFTP y entra al login sin soltar el puerto.

catch_final.py captura N segundos tras `bootm` y cierra COM4.  Lanzarlo y
esperar a que otro proceso abra el puerto deja un hueco de varios segundos,
y la consola de RouterOS solo vive entre ~46 y ~135 s de uptime: en ese
hueco se pierde la ventana (pasó en H26..H36).

Aquí catch_final.py corre como hijo y, en cuanto termina, este mismo
proceso abre COM4 y hace el login.  Nada más escribe en ttyS0: el
postdiag/webdiag van desarmados porque sus volcados abortan la sesión de
`user` con "SCRIPT ERROR: interrupted".

    python -u tools/boot_login.py [segundos-post]

Salida: logs/boot_login.out (cazador) y logs/mikrotik-session.txt (consola).
"""
import os
import subprocess
import sys
import time

import serial

PORT = os.environ.get("ED500_PORT", "COM4")
POST = sys.argv[1] if len(sys.argv) > 1 else "85"
SESION = "logs/mikrotik-session.txt"


def abrir():
    for _ in range(40):
        try:
            return serial.Serial(PORT, 115200, timeout=0.1)
        except Exception:
            time.sleep(0.5)
    return None


def main():
    os.makedirs("logs", exist_ok=True)
    out = open("logs/boot_login.out", "wb")
    rc = subprocess.call([sys.executable, "-u", "catch_final.py",
                          "--post", POST, "--horas", "1"], stdout=out)
    out.close()
    if rc != 0:
        print(f"[!] el cazador salio con {rc}")

    s = abrir()
    if s is None:
        print(f"[!] no pude abrir {PORT}")
        return 1

    log = open(SESION, "wb")

    def leer(seg):
        t = time.time()
        o = b""
        while time.time() - t < seg:
            d = s.read(4096)
            if d:
                o += d
                log.write(d)
                log.flush()
        return o

    def esperar(pals, seg):
        o = b""
        t = time.time()
        while time.time() - t < seg:
            o += leer(0.4)
            if any(p in o.lower() for p in pals):
                break
        return o

    def enviar(txt, pausa=0.07):
        for c in txt.encode():
            s.write(bytes([c]))
            time.sleep(pausa)

    # H34: consola 100% virgen.  Cualquier escritura en ttyS0 mientras
    # user tiene la sesion la aborta con "SCRIPT ERROR: interrupted", asi
    # que aqui no hay volcados: solo se lee y se escribe el login.
    # El prompt puede tardar: se pide repintado sin escribir mas de un \r.
    o = esperar([b"login:"], 20)
    if b"login:" not in o.lower():
        enviar("\r")
        o = esperar([b"login:"], 10)
    print("[i] prompt:", "si" if b"login:" in o.lower() else "NO")

    # Vacia primero: el autorun corre antes de que exista el servicio
    # `user`, asi que `/user set admin password` falla y admin se queda sin
    # contrasena.  Despues ed500, por si el autorun si llego a tiempo.
    for clave, et in (("ed500", "ed500"), ("", "vacia")):
        enviar("admin\r")
        o = esperar([b"assword"], 10)
        if b"assword" not in o.lower():
            print(f"[{et}] no pide contrasena")
            break
        enviar(clave + "\r")
        # 50 s: con el reloj del kernel ya arreglado, los timeouts de
        # RouterOS esperan de verdad; 10-15 s no bastaban para distinguir
        # "autenticando" de "colgado".
        r = leer(40)
        txt = r.decode("utf-8", "replace")
        enterado = "] >" in txt or "> " in txt
        print(f"[{et}] {'SESION' if enterado else 'sin sesion'}: "
              f"{txt.strip()[-200:]!r}")
        if enterado:
            for cmd in ("/system license print",
                        "/system resource print",
                        "/interface print",
                        "/system identity print"):
                enviar(cmd + "\r")
                print(f"--- {cmd} ---")
                print(leer(10).decode("utf-8", "replace")[-1800:])
            break

    # Tras los intentos, seguir leyendo: el init deja un volcado tardio
    # (log interno de RouterOS + store) que solo se ve aqui.
    print("[i] esperando volcado tardio")
    leer(60)

    s.close()
    log.close()
    print(f"[i] consola en {SESION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
