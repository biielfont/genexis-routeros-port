#!/usr/bin/env python3
"""Fallo encontrado al revisar el init: metia en el bridge TODO lo que casara
con lan*/eth*/cbm*, incluido eth0, que es el maestro de DSA. Puentear el
maestro con sus propios puertos rompe el datapath.

Ahora: si hay puertos lan*, se usan solo esos. eth*/cbm* solo si no hay lan*.
"""
import pathlib

F = pathlib.Path("/opt/ros-port/initramfs/init")

OLD_START = '''# --- red: todos los puertos en un bridge ---
BRPORTS=""
for d in /sys/class/net/*; do
	n=${d##*/}
	case "$n" in
		lo|br0) continue ;;
		lan*|eth*|cbm*) BRPORTS="$BRPORTS $n" ;;
	esac
done
'''

NEW_START = '''# --- red: puertos del switch en un bridge ---
# Ojo: eth0/cbm0 es el maestro de DSA; puentearlo con sus propios puertos
# rompe el datapath. Por eso se prefieren los lan* y solo se cae en eth*/cbm*
# cuando no hay puertos DSA.
echo "interfaces:"
for d in /sys/class/net/*; do
	n=${d##*/}
	[ "$n" = "lo" ] && continue
	echo "  $n $(cat /sys/class/net/$n/operstate 2>/dev/null)"
done

BRPORTS=""
for d in /sys/class/net/*; do
	n=${d##*/}
	case "$n" in lan*) BRPORTS="$BRPORTS $n" ;; esac
done
if [ -z "$BRPORTS" ]; then
	for d in /sys/class/net/*; do
		n=${d##*/}
		case "$n" in eth*|cbm*) BRPORTS="$BRPORTS $n" ;; esac
	done
fi
'''


def main():
    s = F.read_text(errors="replace")
    if "puentearlo con sus propios puertos" in s:
        print("ya estaba")
        return
    if OLD_START not in s:
        print("NO: bloque no encontrado")
        return
    F.write_text(s.replace(OLD_START, NEW_START, 1))
    print("ok: init corregido")


if __name__ == "__main__":
    main()
