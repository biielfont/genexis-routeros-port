"""Envia bootm al uImage ya cargado en 0x80500000 y captura el arranque."""
import serial
import time

s = serial.Serial("COM4", 115200, timeout=0.05)
log = open("logs/bootm563.log", "wb")

s.write(b"\r")
time.sleep(0.3)
s.write(b"bootm 0x80500000\r")

t0 = time.time()
buf = b""
while time.time() - t0 < 150:
    d = s.read(4096)
    if d:
        buf += d
        log.write(d)
        log.flush()

s.close()
log.close()

txt = buf.decode("utf-8", "replace")
print("bytes:", len(buf))
print("\n".join(l.strip()[:130] for l in txt.splitlines() if l.strip()).encode(
    "ascii", "replace").decode())
