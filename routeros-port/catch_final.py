"""Caza el prompt de U-Boot tras un ciclo de corriente, carga uImage-563 por
TFTP y lo arranca.

Lleva el servidor TFTP dentro, asi que un solo proceso hace todo: sirve la
imagen, espera a U-Boot, la transfiere, comprueba que el tamano coincide y
hace bootm. No toca la NAND: todo va a RAM.

    python catch_final.py            # ventana de 3 horas
    python catch_final.py --horas 6
"""

import argparse
import os
import sys
import time

import serial
import tftplib

PORT = "COM4"
IMG = "uImage-563"
LOG = "logs/try563_v2.log"


def abrir_puerto():
    for intento in range(10):
        try:
            return serial.Serial(PORT, 115200, timeout=0.02)
        except serial.SerialException as exc:
            if intento == 0:
                print(f"[!] {PORT} ocupado o no existe: {exc}")
                print("    cierra cualquier otra ventana que este usando el puerto.")
            time.sleep(2)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horas", type=float, default=3.0)
    args = ap.parse_args()

    os.makedirs("logs", exist_ok=True)
    log = open(LOG, "wb")

    def w(b):
        log.write(b)
        log.flush()

    def say(txt):
        print(txt, flush=True)

    # --- 1. TFTP ---
    puerto = tftplib.start("out", out=say)
    if puerto is None:
        say("[!] no he podido abrir ningun puerto TFTP (69 ni 6969)")
    elif puerto != 69:
        say(f"sirvo TFTP en {puerto}: se lo dire a U-Boot con tftpdstp")
    tam = os.path.getsize(os.path.join("out", IMG)) if os.path.exists(os.path.join("out", IMG)) else 0
    say(f"imagen: {IMG} ({tam} bytes)")

    # --- 2. puerto serie ---
    s = abrir_puerto()

    def rd(dur):
        t0, out = time.time(), b""
        while time.time() - t0 < dur:
            d = s.read(2048)
            if d:
                out += d
                w(d)
        return out

    def rd_until(needle, dur):
        t0, out = time.time(), b""
        while time.time() - t0 < dur:
            d = s.read(2048)
            if d:
                out += d
                w(d)
                if needle in out:
                    break
        return out

    limite = time.time() + args.horas * 3600
    intento = 0
    say(f"esperando U-Boot hasta {args.horas} h (Ctrl+C para parar)...")

    try:
        while time.time() < limite:
            intento += 1
            caught = _cazar(s, rd, limite)
            if not caught:
                break

            w(f"\n### PROMPT U-BOOT CAZADO (intento {intento}) ###\n".encode())
            say(f"prompt cazado (intento {intento}): cargando por TFTP")
            _arrancar(s, rd, rd_until, w, say, puerto, tam)

            if time.time() >= limite:
                break
            say("vuelvo a esperar por si la placa se reinicia...")
    except KeyboardInterrupt:
        say("\nparado a mano")
    finally:
        s.close()
        log.close()


def _cazar(s, rd, limite):
    buf = b""
    try:
        while time.time() < limite:
            s.write(b"\r")
            buf += rd(0.03)
            if b"grx500 #" in buf:
                return True
            if len(buf) > 200000:
                buf = buf[-100000:]
    except KeyboardInterrupt:
        raise
    return False


def _arrancar(s, rd, rd_until, w, say, puerto, tam):



    time.sleep(0.3)
    # fijar servidor y puerto, para no depender de lo que quede en el entorno
    s.write(b"setenv ipaddr 192.168.1.1\r")
    rd_until(b"#", 3)
    s.write(b"setenv serverip 192.168.1.160\r")
    rd_until(b"#", 3)
    if puerto and puerto != 69:
        s.write(b"setenv tftpdstp " + str(puerto).encode() + b"\r")
        rd_until(b"#", 3)
    s.write(b"tftpboot 0x80500000 " + IMG.encode() + b"\r")
    out = rd_until(b"Bytes transferred", 60)
    w(b"\n### FIN TFTP ###\n")

    if b"Bytes transferred" not in out:
        w(b"\n### TFTP NO CONFIRMADO ###\n")
        say("TFTP no confirmo la transferencia; no arranco")
        return

    # --- 4. comprobar tamano ---
    try:
        linea = [l for l in out.split(b"\n") if b"Bytes transferred" in l][-1]
        n = int(linea.split(b"= ")[1].split(b" ")[0])
    except Exception:  # noqa: BLE001
        n = -1
    if tam and n not in (-1, tam):
        w(f"\n### TAMANO DISTINTO: {n} != {tam} ###\n".encode())
        say(f"AVISO: transferidos {n} bytes, el fichero tiene {tam}")
    else:
        say(f"transferidos {n} bytes (coincide)")

    # --- 5. arrancar ---
    say("bootm...")
    time.sleep(0.3)
    s.write(b"bootm 0x80500000\r")
    salida = rd(300)
    w(b"\n### FIN bootm ###\n")

    # --- 6. veredicto, para no tener que leer el log entero ---
    veredicto = _veredicto(salida)
    w(f"\n### VEREDICTO: {veredicto} ###\n".encode())
    say(f"veredicto: {veredicto}")
    say(f"consola completa en {LOG}")


def _veredicto(salida):
    if b"Linux version 5.6.3" not in salida:
        if b"Kernel panic" in salida or b"Oops" in salida:
            return "PANIC/OOPS antes del banner"
        if b"Bytes transferred" in salida and len(salida) < 400:
            return "bootm mudo: no hay ni una linea de kernel"
        return "el kernel no ha llegado a imprimir su version"
    if b"Kernel panic" in salida:
        return "arranco e hizo PANIC"
    partes = ["arranco"]
    for clave, txt in ((b"gswip", "switch"), (b"lan1", "lan1"),
                       (b"red: ", "red"), (b"web: http", "http")):
        if clave in salida:
            partes.append(txt)
    if b"Kernel panic" not in salida and b"red: 192.168" in salida:
        partes.append("shell")
    return " + ".join(partes)


if __name__ == "__main__":
    main()
