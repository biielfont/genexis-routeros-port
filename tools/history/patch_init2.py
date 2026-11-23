#!/usr/bin/env python3
"""El busybox del initramfs NO tiene: ip, awk, wc.
Tiene: ifconfig, route, brctl, udhcpc, httpd, telnetd, sleep.

Se reescribe la seccion de red para no usar lo que falta. Esto era un fallo
real: el init llamaba a `ip link set` y fallaba en silencio, asi que el router
arrancaba sin IP y sin forma de entrar.
"""
import pathlib
import re

F = pathlib.Path("/opt/ros-port/initramfs/init")

NEW = r'''# --- red: todos los puertos en un bridge ---
BRPORTS=""
for d in /sys/class/net/*; do
	n=${d##*/}
	case "$n" in
		lo|br0) continue ;;
		lan*|eth*|cbm*) BRPORTS="$BRPORTS $n" ;;
	esac
done

COUNT=0
for n in $BRPORTS; do COUNT=$((COUNT + 1)); done

if [ "$COUNT" -eq 0 ]; then
	echo "red: no hay interfaces (el driver Ethernet no ha creado ninguna)"
	iface=""
else
	echo "red: puertos:$BRPORTS"
	for n in $BRPORTS; do
		ifconfig "$n" up 2>/dev/null
	done

	# un solo puerto -> directo; varios -> bridge (asi da igual la boca)
	if [ "$COUNT" -ge 2 ] && command -v brctl >/dev/null 2>&1; then
		brctl addbr br0 2>/dev/null
		for n in $BRPORTS; do
			brctl addif br0 "$n" 2>/dev/null
		done
		ifconfig br0 up 2>/dev/null
		iface=br0
	else
		for n in $BRPORTS; do iface=$n; break; done
	fi

	echo "red: usando $iface"
	if command -v udhcpc >/dev/null 2>&1; then
		udhcpc -i "$iface" -t 3 -T 2 -n -q >/tmp/dhcp.log 2>&1
	fi

	CUR_IP=""
	if ifconfig "$iface" 2>/dev/null | grep -q "inet addr"; then
		CUR_IP=$(ifconfig "$iface" | sed -n 's/.*inet addr:\([0-9.]*\).*/\1/p' | head -1)
	fi

	if [ -z "$CUR_IP" ]; then
		echo "red: sin DHCP, IP fija $STATIC_IP/$STATIC_MASK"
		ifconfig "$iface" "$STATIC_IP" netmask 255.255.255.0 up 2>/dev/null
		[ -n "$STATIC_GW" ] && route add default gw "$STATIC_GW" 2>/dev/null
		CUR_IP=$STATIC_IP
	fi

	echo "red: $CUR_IP en $iface"
fi
[ -z "${CUR_IP:-}" ] && CUR_IP=$STATIC_IP
'''


def main():
    s = F.read_text(errors="replace")
    pat = re.compile(r"# --- red: todos los puertos en un bridge ---.*?\[ -z \"\$\{CUR_IP:-\}\" \] && CUR_IP=\$STATIC_IP\n", re.S)
    if not pat.search(s):
        print("NO: bloque de red no encontrado")
        return
    s = pat.sub(lambda m: NEW, s, count=1)
    F.write_text(s)
    print("ok: init reescrito sin ip/awk/wc")
    for bad in ("ip link", "ip addr", "ip route", "awk", "wc -"):
        if bad in s:
            print("OJO: sigue habiendo", bad)


if __name__ == "__main__":
    main()
