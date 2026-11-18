#!/usr/bin/env python3
"""Caza el prompt del U-Boot del ED500.

Manda CR sin parar (cada 30 ms) desde que arranca el script, asi que da igual
cuando enciendas el router: alguna tecla cae dentro de la ventana de autoboot.
En cuanto ve el prompt (=>) deja de martillear y se queda escuchando, con
stdin conectado al puerto para poder escribir comandos.

Uso: python ubootcatch.py COM4 115200 logs/uboot.log
"""
import re
import sys
import threading
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
logpath = sys.argv[3] if len(sys.argv) > 3 else None

log = open(logpath, "ab", buffering=0) if logpath else None
ser = serial.Serial(port, baud, timeout=0.05)
print(f"[catch] {port} abierto, martilleando CR hasta ver el prompt", flush=True)

got_prompt = threading.Event()
PROMPT = re.compile(rb"(=>\s*$|U-Boot>\s*$)")


def reader():
    buf = b""
    while True:
        try:
            data = ser.read(2048)
        except Exception as e:
            print(f"[catch] error lectura: {e}", flush=True)
            return
        if not data:
            continue
        if log:
            log.write(data)
        sys.stdout.write(data.decode("utf-8", "replace"))
        sys.stdout.flush()
        buf = (buf + data)[-200:]
        if not got_prompt.is_set() and PROMPT.search(buf):
            got_prompt.set()
            print("\n[catch] *** PROMPT DE U-BOOT DETECTADO *** (teclas paradas)", flush=True)


def spam():
    t0 = time.time()
    n = 0
    while not got_prompt.is_set() and time.time() - t0 < 600:
        try:
            ser.write(b"\r")
            n += 1
        except Exception:
            return
        time.sleep(0.03)
    print(f"[catch] fin del martilleo ({n} CR enviados)", flush=True)


threading.Thread(target=reader, daemon=True).start()
threading.Thread(target=spam, daemon=True).start()

try:
    for line in sys.stdin:
        ser.write(line.rstrip("\n").encode() + b"\r")
        ser.flush()
        print(f"\n[catch] -> {line.rstrip()}", flush=True)
except KeyboardInterrupt:
    pass
