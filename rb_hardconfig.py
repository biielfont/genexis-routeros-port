#!/usr/bin/env python3
"""Genera un RouterBoot hard_config sintetico para el ED500.

flash.ko (propietario) exige un MTD llamado RouterBoot y lee de el una
cabecera con el puntero/tamano del hard config y un bloque "Hard" con TLVs.
El mtdram arranca en 0xFF, asi que flash.ko lee 0xFFFFFFFF como tamano,
vmalloc falla y no se crea /dev/flash. Este script fabrica una identidad
minima (product ID 000, MAC real del ED500, serial real) y un bloque de
64 KiB que el init escribe en /dev/mtdblock0 antes de sysinit.

No toca la NAND ni la licencia: es identidad volatil en RAM, igual que la
que genera RouterOS al instalarse en x86/arm64.
"""

import struct
import sys

MAGIC = 0x64726148  # "Hard" leido como u32 big-endian (bytes 64 72 61 48)


def be32(valor):
    return struct.pack(">I", valor & 0xFFFFFFFF)


def tlv(tag, payload):
    """Nodo TLV RouterBoot: tag en 16 bits bajos, longitud en altos."""
    relleno = b"\0" * ((-len(payload)) % 4)
    return be32((len(payload) << 16) | tag) + payload + relleno


def soft_config():
    """Bloque Soft de RouterBoot.

    flash.ko copia soft_size bytes desde soft_ptr y comprueba que la
    primera palabra sea 0x74666f53 ("Soft" leido como u32). En mipsbe
    eso son los bytes 74 66 6f 53. Los TLVs usan el mismo formato que
    el hard config: tag en 16 bits bajos y longitud en bytes en los
    altos. La geometria viene del RouterBOOT de referencia; el mtdram
    solo necesita un bloque coherente para que flash.ko cree /dev/flash.
    """
    entradas = [
        (12, be32(0x370)),
        (17, be32(0x4B0)),
        (10, be32(0x370)),
        (1, be32(0)),
        (2, be32(2)),
        (3, be32(1)),
        (4, be32(0)),
        (5, be32(0)),
        (7, be32(0)),
        (9, be32(0)),
        (15, be32(0)),
        (21, be32(0)),
        (23, be32(0)),
        (27, be32(0)),
        (31, be32(0x140258)),
        (32, be32(0)),
        (13, be32(0)),
        (6, b"6.47.4\0\0"),
        (11, b"j1" + b"\0" * 6),
    ]
    # Palabra 0: magic. Palabra 1: checksum/version (el driver empieza a
    # parsear en la palabra 2, igual que el soft_config real).
    soft = be32(0x74666F53) + be32(0)  # "Soft" como u32 big-endian
    for tag, payload in entradas:
        soft += tlv(tag, payload)
    return soft.ljust(0x1000, b"\0")


def build():
    # MAC real del Pure ED500 (U-Boot env). El hard config la guarda como
    # dos palabras de 32 bits; en mipsbe los bytes van en orden de memoria.
    mac = bytes.fromhex("34e380c377f0")

    tags = [
        # get_rb_pid() pide primero la etiqueta 44; 000 = sin product ID.
        (44, be32(0)),
        (4, mac + b"\0\0"),                  # MAC base, 8 bytes
        (5, b"PureED500\0\0\0"),             # nombre de placa, 12 bytes
        (11, b"W.3620220010\0\0\0\0"),       # serial del ED500, 16 bytes
        (33, b"ED5\0"),                      # nombre de producto
        (23, b"ed500" + b"\0" * 7),          # modelo, 12 bytes
        (6, b"6.47.4\0\0"),                  # version del booter
        (14, be32(5)),                       # tipo de flash
        (26, be32(0)),
        (10, be32(0)),
        (13, be32(0x10000000)),
        (19, be32(0)),
        (18, be32(0x00030000)),
        (20, be32(0)),
        (21, be32(0)),
        (27, be32(0x1388)),
        (25, b"\0" * 20),
        (3, b"\0" * 20),
    ]

    hard = be32(MAGIC) + b"".join(tlv(t, p) for t, p in tags)
    if len(hard) > 0x1000:
        raise SystemExit("hard config demasiado grande: %d" % len(hard))
    hard = hard.ljust(0x1000, b"\0")

    # La cabecera RouterBoot no tiene marca conocida; flash.ko lee de ella
    # puntero y tamano. Se rellenan las variantes de 16 y 32 MiB (s0=16/32)
    # y se dejan BIOS/soft config a NULL. Las copias del bloque van a 0x1000
    # y 0xf000, que son los dos offsets que usan los RouterBOOT reales.
    soft = soft_config()
    img = bytearray(b"\xff" * 0x10000)
    cabecera = {
        0x00: 0x10000009,  # marca/version RouterBoot
        0x14: 0xF000,      # hard_ptr si s0=0 (cabecera real)
        0x18: 0x1000,      # hard_size si s0=0/16
        0x1C: 0x8000,      # soft_ptr (o soft_size si van invertidos)
        0x20: 0x8000,      # soft_size (o soft_ptr si van invertidos)
        0x24: 0x1000,      # hard_ptr si s0=16
        0x28: 0x1000,      # hard_size si s0=32
        0x2C: 0x8000,      # soft_ptr/size si s0=32
        0x30: 0x8000,      # soft_size/ptr si s0=32
        0x34: 0x1000,      # hard_ptr si s0=32
    }
    for off, valor in cabecera.items():
        img[off:off + 4] = be32(valor)

    img[0x1000:0x2000] = hard
    img[0x8000:0x9000] = soft
    img[0xF000:0x10000] = hard
    return bytes(img)


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "rb_hardconfig.bin"
    data = build()
    with open(salida, "wb") as f:
        f.write(data)
    print("%s: %d bytes (hard config en 0x1000 y 0xf000)" % (salida, len(data)))


if __name__ == "__main__":
    main()
