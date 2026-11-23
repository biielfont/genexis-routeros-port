#!/usr/bin/env python3
"""Terminal serie con log, para COM4 @115200 (U-Boot / consola del ED500).

Uso:  python serialterm.py COM4 115200 logs/uboot.log
Escribe en stdin -> se manda al puerto al pulsar Enter (CR, como U-Boot).
Todo lo recibido se imprime y se guarda en el log.
Por defecto NO envia nada al abrir: solo escucha, que es lo que queremos
mientras el router arranca.
"""
import sys, os, time, threading

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
logpath = sys.argv[3] if len(sys.argv) > 3 else None

if logpath:
    os.makedirs(os.path.dirname(logpath) or ".", exist_ok=True)
    log = open(logpath, "ab", buffering=0)
else:
    log = None

ser = serial.Serial(port, baud, bytesize=8, parity="N", stopbits=1, timeout=0.2)
print(f"[serial] {port} @ {baud} 8N1 abierto" + (f", log -> {logpath}" if logpath else ""), flush=True)


last_rx = [time.time()]
armed = [True]


def interrupt_burst():
    """U-Boot corta el autoboot con cualquier tecla; el arranque empieza con
    una rafaga de basura del bootloader, asi que en cuanto llega el primer
    byte enviamos teclas durante unos segundos para caer en el prompt."""
    print("\n[serial] actividad detectada -> enviando teclas para cortar autoboot", flush=True)
    for _ in range(40):
        try:
            ser.write(b"\r")
        except Exception:
            return
        time.sleep(0.15)
    print("[serial] rafaga terminada (prompt U-Boot)", flush=True)


def reader():
    while True:
        try:
            data = ser.read(4096)
        except Exception as e:            # desconexion / error de driver
            print(f"[serial] ERROR lectura: {e}", flush=True)
            return
        if data:
            if log:
                log.write(data)
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()
            # primera actividad tras un silencio largo = el router acaba de encender
            if armed[0] and "noint" not in sys.argv and time.time() - last_rx[0] > 2.0:
                armed[0] = False
                threading.Thread(target=interrupt_burst, daemon=True).start()
            last_rx[0] = time.time()


threading.Thread(target=reader, daemon=True).start()

try:
    for line in sys.stdin:
        # comandos: se envian tal cual + CR (U-Boot usa CR, no LF)
        ser.write(line.rstrip("\n").encode() + b"\r")
        ser.flush()
        print(f"\n[serial] -> {line.rstrip()}", flush=True)
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    if log:
        log.close()
