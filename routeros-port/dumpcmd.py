#!/usr/bin/env python3
"""Manda un comando y guarda la salida CRUDA en un fichero.

Uso: python dumpcmd.py "fdt print" 50 logs/out.txt
Evita el problema de codificacion de la consola de Windows (cp1252).
"""
import sys
import time

import serial

cmd = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
out = sys.argv[3] if len(sys.argv) > 3 else "logs/dump.txt"

ser = serial.Serial("COM4", 115200, timeout=0.1)
time.sleep(0.2)
for line in cmd.split("\\n"):
    ser.write(line.encode() + b"\r")
    ser.flush()
    time.sleep(0.3)

buf = b""
t0 = time.time()
while time.time() - t0 < secs:
    d = ser.read(8192)
    if d:
        buf += d
ser.close()

with open(out, "wb") as f:
    f.write(buf)
print(f"{len(buf)} bytes -> {out}")
