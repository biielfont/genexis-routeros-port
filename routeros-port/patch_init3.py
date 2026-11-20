#!/usr/bin/env python3
"""Si el switch/conduit no crean interfaces, que el init lo diga:
imprime las lineas de dmesg relacionadas. Asi una foto de la consola
basta para saber si fallo el GSWIP, el CBM o el enlace del PHY.
"""
import pathlib

F = pathlib.Path("/opt/ros-port/initramfs/init")

OLD = '''if [ "$COUNT" -eq 0 ]; then
	echo "red: no hay interfaces (el driver Ethernet no ha creado ninguna)"
	iface=""'''

NEW = '''if [ "$COUNT" -eq 0 ]; then
	echo "red: no hay interfaces (el driver Ethernet no ha creado ninguna)"
	echo "--- dmesg: switch / conduit / phy ---"
	dmesg 2>/dev/null | grep -iE "gswip|cbm|xrx|conduit|mdio|phy|dsa" | tail -25
	iface=""'''


def main():
    s = F.read_text(errors="replace")
    if NEW in s:
        print("ya estaba")
        return
    if OLD not in s:
        print("NO: bloque no encontrado")
        return
    F.write_text(s.replace(OLD, NEW, 1))
    print("ok: diagnostico anadido")


if __name__ == "__main__":
    main()
