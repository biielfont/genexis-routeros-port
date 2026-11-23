"""Caza el prompt de U-Boot tras un ciclo de corriente, carga uImage-563 por
TFTP y lo arranca. Espera a ver 'Bytes transferred' antes de lanzar bootm.
No toca la NAND: todo va a RAM."""
import serial
import time

PORT = "COM4"
IMG = "uImage-563"
LOG = "logs/try563_v2.log"

s = serial.Serial(PORT, 115200, timeout=0.02)
log = open(LOG, "wb")


def w(b):
    log.write(b)
    log.flush()


def rd(dur):
    t0 = time.time()
    out = b""
    while time.time() - t0 < dur:
        d = s.read(2048)
        if d:
            out += d
            w(d)
    return out


def rd_until(needle, dur):
    t0 = time.time()
    out = b""
    while time.time() - t0 < dur:
        d = s.read(2048)
        if d:
            out += d
            w(d)
            if needle in out:
                break
    return out


buf = b""
t0 = time.time()
caught = False
while time.time() - t0 < 900:
    s.write(b"\r")
    d = rd(0.03)
    buf += d
    if b"grx500 #" in buf:
        caught = True
        break

if not caught:
    w(b"\n### NO SE CAZO U-BOOT ###\n")
    s.close()
    log.close()
    raise SystemExit

w(b"\n### PROMPT U-BOOT CAZADO ###\n")
time.sleep(0.2)
s.write(b"tftpboot 0x80500000 " + IMG.encode() + b"\r")
out = rd_until(b"Bytes transferred", 45)
w(b"\n### FIN TFTP ###\n")

if b"Bytes transferred" in out:
    time.sleep(0.3)
    s.write(b"bootm 0x80500000\r")
    rd(180)
    w(b"\n### FIN bootm ###\n")
else:
    w(b"\n### TFTP NO CONFIRMADO ###\n")

s.close()
log.close()
