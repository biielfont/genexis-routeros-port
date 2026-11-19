#!/usr/bin/env python3
"""Manda comandos a la consola serie del ED500 y devuelve lo que responde.

    python consola.py "ls /sys/class/net" "dmesg | tail -30"

Necesita COM4 libre: si el cazador esta corriendo, paralo antes.
"""

import os
import sys
import time

import serial

PORT = "COM4"
ESPERA = float(os.environ.get("ESPERA", "4"))   # segundos por comando


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    s = serial.Serial(PORT, 115200, timeout=0.05)
    try:
        time.sleep(0.3)
        s.reset_input_buffer()
        s.write(b"\r")            # despertar el prompt
        time.sleep(0.6)
        s.reset_input_buffer()

        for cmd in sys.argv[1:]:
            print(f"\n$ {cmd}")
            s.write(cmd.encode() + b"\r")
            t0, buf = time.time(), b""
            while time.time() - t0 < ESPERA:
                d = s.read(4096)
                if d:
                    buf += d
            sys.stdout.write(buf.decode(errors="replace"))
            sys.stdout.flush()
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
