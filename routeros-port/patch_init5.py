#!/usr/bin/env python3
"""Si no hay consola pero si red, el log del arranque se puede leer por HTTP.
Se vuelca dmesg en /www (servido por httpd) y se refresca cada 30 s.
"""
import pathlib

F = pathlib.Path("/opt/ros-port/initramfs/init")

OLD = '''echo
echo "estado: http://$CUR_IP/   ·   consola: ttyLTQ0"'''

NEW = '''# --- log accesible por web (para cuando no hay consola) ---
dmesg > /www/dmesg.txt 2>/dev/null
{
	echo "hostname: $HOSTNAME"
	echo "kernel:   $(uname -a)"
	echo "ip:       $CUR_IP en $iface"
	echo
	echo "== interfaces =="
	ifconfig -a 2>/dev/null
	echo
	echo "== rutas =="
	route -n 2>/dev/null
	echo
	echo "== bridge =="
	brctl show 2>/dev/null
} > /www/estado.txt 2>/dev/null
(
	while true; do
		sleep 30
		dmesg > /www/dmesg.txt 2>/dev/null
	done
) &

echo
echo "estado: http://$CUR_IP/   ·   consola: ttyLTQ0"
echo "log del arranque: http://$CUR_IP/dmesg.txt"'''


def main():
    s = F.read_text(errors="replace")
    if "dmesg.txt" in s:
        print("ya estaba")
        return
    if OLD not in s:
        print("NO: bloque no encontrado")
        return
    F.write_text(s.replace(OLD, NEW, 1))
    print("ok: log web anadido")


if __name__ == "__main__":
    main()
