"""Reinicia el router en modo forzado y captura todo lo que sale por la consola
para localizar la ventana de U-Boot con tiempos reales."""
import serial
import time

s = serial.Serial("COM4", 115200, timeout=0.05)
log = open("logs/rebootdiag.log", "wb")

s.write(b"\r")
time.sleep(0.5)
s.write(b"reboot -f\r")
t0 = time.time()
marks = []
buf = b""
while time.time() - t0 < 70:
    d = s.read(2048)
    if d:
        buf += d
        log.write(d)
        log.flush()
        marks.append((round(time.time() - t0, 1), d.decode("utf-8", "replace")))

s.close()
log.close()

txt = buf.decode("utf-8", "replace")
print("bytes capturados:", len(buf))
# mostrar la primera parte, que es donde esta U-Boot
print(txt[:2500])
print("--- ultimos tiempos ---")
for t, d in marks[-5:]:
    print(t, repr(d[-80:]))
