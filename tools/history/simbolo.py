#!/usr/bin/env python3
"""Resuelve direcciones de un Oops contra System.map del kernel 5.6.3.

    python3 simbolo.py 807d9a2c 80777874
"""

import bisect
import os
import sys

ARBOL = "/opt/ros-port/linux-5.6.3"


def cargar(ruta):
    syms = []
    with open(ruta) as f:
        for linea in f:
            partes = linea.split(None, 2)
            if len(partes) == 3:
                syms.append((int(partes[0], 16) & 0xFFFFFFFF,
                             partes[2].strip()))
    syms.sort()
    return syms


def main():
    syms = cargar(os.path.join(ARBOL, "System.map"))
    addrs = [s[0] for s in syms]
    for arg in sys.argv[1:]:
        # el log trae direcciones de 32 bits; System.map las lleva con
        # el prefijo 0xffffffff, asi que se comparan enmascaradas.
        x = int(arg, 16) & 0xFFFFFFFF
        i = bisect.bisect_right(addrs, x) - 1
        print(f"{x:#010x}  {syms[i][1]}+{x - syms[i][0]:#x}")


if __name__ == "__main__":
    main()
