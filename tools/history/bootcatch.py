#!/usr/bin/env python3
"""Martillea CR unos segundos (para cortar el autoboot de 3 s) y luego lee.

Uso: python bootcatch.py [segundos_teclas] [segundos_lectura]
"""
import sys
import time

import serial

keys = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
read = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0

ser = serial.Serial("COM4", 115200, timeout=0.05)
time.sleep(0.2)
t0 = time.time()
while time.time() - t0 < keys:
    ser.write(b"\r")
    time.sleep(0.03)

buf = b""
t0 = time.time()
while time.time() - t0 < read:
    d = ser.read(4096)
    if d:
        buf += d
ser.close()
sys.stdout.write(buf.decode("utf-8", "replace"))
