#!/usr/bin/env python3
"""TFTP server para que el U-Boot del ED500 cargue nuestro kernel sin flashear.

Uso:  python tftpd.py out
Sirve el directorio indicado en 0.0.0.0:69 (el puerto que usa U-Boot).
Si Windows pregunta por el firewall, hay que permitirlo en red privada.
"""
import logging
import os
import sys

import tftpy

root = sys.argv[1] if len(sys.argv) > 1 else "out"
root = os.path.abspath(root)
logging.basicConfig(level=logging.INFO, format="[tftp] %(asctime)s %(message)s", datefmt="%H:%M:%S")

server = tftpy.TftpServer(root)
print(f"[tftp] sirviendo {root} en 0.0.0.0:69", flush=True)
server.listen("0.0.0.0", 69)
