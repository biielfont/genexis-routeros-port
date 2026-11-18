#!/usr/bin/env python3
"""Manda un comando por COM4 y captura la respuesta (un solo disparo).

Uso:  python sendcmd.py "printenv" [segundos] [COM4] [baud]
Evita el problema de stdin del proceso interactivo: abre, escribe, lee, cierra.
"""
import sys
import time

import serial

cmd = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
port = sys.argv[3] if len(sys.argv) > 3 else "COM4"
baud = int(sys.argv[4]) if len(sys.argv) > 4 else 115200

ser = serial.Serial(port, baud, timeout=0.1)
time.sleep(0.2)
for line in cmd.split("\\n"):
    ser.write(line.encode() + b"\r")
    ser.flush()
    time.sleep(0.2)

buf = b""
t0 = time.time()
while time.time() - t0 < secs:
    data = ser.read(4096)
    if data:
        buf += data
ser.close()

import os as _os; _os.makedirs("logs", exist_ok=True)
with open("logs/serial-cmd.log", "ab") as f:
    f.write(buf)

sys.stdout.write(buf.decode("utf-8", "replace"))
