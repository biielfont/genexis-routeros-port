"""Espera al arranque del router, caza el prompt de U-Boot machacando CR y,
en cuanto lo ve, carga el uImage del 5.6.3 por TFTP y lo arranca.

Pensado para lanzarse en segundo plano y hacer un ciclo de corriente.
Todo va a RAM: no toca la NAND.
"""
import serial
import time

PORT = "COM4"
IMG = "uImage-563"
LOG = "logs/try563_long.log"

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

if caught:
    w(b"\n### PROMPT U-BOOT CAZADO ###\n")
    time.sleep(0.3)
    s.write(b"tftpboot 0x80500000 " + IMG.encode() + b"\r")
    out = rd(30)
    w(b"\n### FIN TFTP ###\n")
    if b"Bytes transferred" in out or b"Loading:" in out:
        s.write(b"bootm 0x80500000\r")
        rd(180)
        w(b"\n### FIN BOOTM ###\n")
    else:
        w(b"\n### TFTP NO COMPLETO ###\n")
else:
    w(b"\n### NO SE CAZO U-BOOT EN 180s ###\n")

s.close()
log.close()
