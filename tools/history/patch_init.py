#!/usr/bin/env python3
"""Reescribe la seccion de red del initramfs: en vez de coger la primera
interfaz que aparezca, junta todos los puertos lan*/eth*/cbm* en un bridge
(br0). Asi da igual en que boca este el cable, que es lo que necesitamos
para entrar al router sin consola."""
import pathlib
import re

F = pathlib.Path("/opt/ros-port/initramfs/init")

NEW = r'''# --- red: todos los puertos en un bridge ---
ip link set lo up 2>/dev/null

BRPORTS=""
for d in /sys/class/net/*; do
	n=$(basename "$d")
	case "$n" in
		lo|br0) continue ;;
		lan*|eth*|cbm*) BRPORTS="$BRPORTS $n" ;;
	esac
done

if [ -z "$BRPORTS" ]; then
	echo "red: no hay interfaces (el driver Ethernet no ha creado ninguna)"
	iface=""
else
	echo "red: puertos:$BRPORTS"
	for n in $BRPORTS; do
		ip link set "$n" up 2>/dev/null
	done

	# bridge si hay con que, y si no, el primer puerto
	if command -v brctl >/dev/null 2>&1 && [ "$(echo $BRPORTS | wc -w)" -ge 1 ]; then
		brctl addbr br0 2>/dev/null
		for n in $BRPORTS; do
			brctl addif br0 "$n" 2>/dev/null
		done
		ip link set br0 up 2>/dev/null
		iface=br0
	else
		iface=$(echo $BRPORTS | awk '{print $1}')
	fi

	echo "red: usando $iface"
	if command -v udhcpc >/dev/null 2>&1; then
		udhcpc -i "$iface" -t 3 -T 2 -n -q >/tmp/dhcp.log 2>&1
	fi
	if ! ip -4 addr show "$iface" 2>/dev/null | grep -q "inet "; then
		echo "red: sin DHCP, IP fija $STATIC_IP/$STATIC_MASK"
		ip addr add "$STATIC_IP/$STATIC_MASK" dev "$iface" 2>/dev/null
		[ -n "$STATIC_GW" ] && ip route add default via "$STATIC_GW" 2>/dev/null
	fi
	CUR_IP=$(ip -4 addr show "$iface" 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
	echo "red: ${CUR_IP:-sin ip} en $iface"
fi
[ -z "${CUR_IP:-}" ] && CUR_IP=$STATIC_IP
'''


def main():
    s = F.read_text(errors="replace")
    pat = re.compile(r"# --- red: primero DHCP.*?\[ -z \"\$\{CUR_IP:-\}\" \] && CUR_IP=\$STATIC_IP\n", re.S)
    if not pat.search(s):
        print("NO: bloque de red no encontrado")
        return
    s = pat.sub(NEW, s, count=1)
    F.write_text(s)
    print("ok: init parcheado")


if __name__ == "__main__":
    main()
