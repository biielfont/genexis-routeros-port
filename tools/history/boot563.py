"""Arranca el uImage del 5.6.3 por TFTP en el ED500.

Flujo: reboot -> machacar CR para entrar en U-Boot (bootdelay=3) ->
tftpboot 0x80500000 uImage-563 -> bootm 0x80500000 -> capturar consola.
No escribe en NAND: todo va a RAM.
"""
import serial
import sys
import time

PORT = "COM4"
LOG = "logs/boot563.log"

s = serial.Serial(PORT, 115200, timeout=0.05)
log = open(LOG, "wb")


def w(b):
    log.write(b)
    log.flush()


def rd(dur):
    t0 = time.time()
    out = b""
    while time.time() - t0 < dur:
        d = s.read(1024)
        if d:
            out += d
            w(d)
    return out


print("-> reboot")
s.write(b"\r")
time.sleep(0.4)
s.write(b"reboot\r")

print("-> buscando prompt de U-Boot")
buf = b""
t0 = time.time()
caught = False
while time.time() - t0 < 75:
    s.write(b"\r")
    d = rd(0.03)
    buf += d
    if b"grx500 #" in buf or b"grx500#" in buf:
        caught = True
        break
    if b"~ #" in buf[-200:]:
        # volvio al shell del kernel: no se cazo la ventana
        break

print("prompt U-Boot:", caught)

if caught:
    time.sleep(0.3)
    print("-> tftpboot")
    s.write(b"tftpboot 0x80500000 uImage-563\r")
    out = rd(25)
    print(out.decode("utf-8", "replace")[-500:])
    if b"Bytes transferred" in out or b"Loading:" in out:
        print("-> bootm")
        s.write(b"bootm 0x80500000\r")
        out2 = rd(120)
        tail = out2.decode("utf-8", "replace")
        print(tail[-2500:])
    else:
        print("TFTP no completo")
else:
    print("no se entro en U-Boot; ultimas lineas:")
    print(buf.decode("utf-8", "replace")[-400:])

s.close()
log.close()
