#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

# 1 = arrancar el bash de RouterOS en vez de su sysinit, para inspeccionar
# el sistema desde dentro (interfaces, licencia, modulos) sin reiniciar.
ROS_SHELL=1

mount -t proc     proc     /proc
mount -t sysfs    sysfs    /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null
[ -c /dev/console ] || mknod /dev/console c 5 1 2>/dev/null

# --- RouterOS: si el squashfs va en el initramfs, arrancarlo ---
# El rootfs sale del npk oficial mipsbe (mismo 5.6.3 y mismo vermagic que
# este kernel). Se monta por loop y se cede el testigo a /sbin/sysinit.
if [ -f /ros.squashfs ]; then
	echo "--- RouterOS: montando rootfs ---"
	# RouterOS escribe en / y en /flash/rw (config, logs, ident). El squashfs
	# es de solo lectura, asi que va debajo de un overlay con tmpfs encima.
	mkdir -p /newroot
	if mount -t tmpfs tmpfs /newroot 2>/dev/null \
	   && mkdir -p /newroot/rom /newroot/upper /newroot/work /newroot/merged \
	   && losetup /dev/loop0 /ros.squashfs 2>/dev/null \
	   && mount -t squashfs -o ro /dev/loop0 /newroot/rom 2>/dev/null \
	   && mount -t overlay overlay \
		-o lowerdir=/newroot/rom,upperdir=/newroot/upper,workdir=/newroot/work \
		/newroot/merged 2>/dev/null; then
		echo "  overlay listo, arrancando /sbin/sysinit"
		R=/newroot/merged
		mount -t proc   proc   $R/proc
		mount -t sysfs  sysfs  $R/sys
		mount -t devtmpfs devtmpfs $R/dev 2>/dev/null
		mkdir -p $R/dev/pts $R/dev/shm $R/ram $R/rw $R/flash/rw $R/tmp
		mount -t devpts devpts $R/dev/pts 2>/dev/null
		mount -t tmpfs  tmpfs  $R/ram 2>/dev/null
		mount -t tmpfs  tmpfs  $R/rw 2>/dev/null
		mount -t tmpfs  tmpfs  $R/tmp 2>/dev/null
		mount -t tmpfs  tmpfs  $R/flash/rw 2>/dev/null
		[ -e $R/dev/flash ] || ln -sf /dev/mtdblock0 $R/dev/flash 2>/dev/null
		# RouterOS calcula la validez de su licencia demo con el reloj del
		# sistema. El GRX350 arranca sin RTC util y el kernel cae en 2010,
		# con lo que RouterOS dice "Demo license expired!" y se para. Se
		# fija una fecha moderna antes de cederle el control.
		date -s "2026-11-19 12:00:00" >/dev/null 2>&1
		hwclock -w >/dev/null 2>&1
		echo "  fecha: $(date)"
		# RouterOS abre la consola por el nombre generico ttyS*; en este
		# SoC el puerto es el ASC de Lantiq (ttyLTQ0).
		for n in 0 1 2 3; do
			[ -e $R/dev/ttyS$n ] || ln -sf ttyLTQ0 $R/dev/ttyS$n 2>/dev/null
		done
		# Diagnostico: por que no cargan los modulos de red de RouterOS.
		# El insmod de su sysinit solo dice "failed: 2"; el del kernel
		# imprime el simbolo que falta.
		echo "--- diagnostico modulos de red de RouterOS ---"
		for m in drivers/net/packet_hook.ko drivers/net/phy_helper.ko \
		         drivers/net/switch.ko net/bridge/bridge2.ko; do
			echo "  == $m"
			insmod $R/lib/modules/5.6.3/$m 2>&1 | head -8
		done
		echo "--- fin diagnostico ---"
		# Modo inspeccion: arrancar un shell dentro del rootfs de
		# RouterOS (trae bash) para ver estado, interfaces y licencia
		# sin necesidad de reiniciar a ciegas.
		# El bash de RouterOS vive en /pckg/option, que solo existe cuando
		# sus paquetes estan montados; en el rootfs base no esta. Se copia
		# el busybox estatico del initramfs al overlay y se arranca ese,
		# con / como root de RouterOS.
		if [ "$ROS_SHELL" = 1 ]; then
			# Tiene que llamarse "busybox": el binario elige el applet por
			# el nombre con el que se invoca; con otro nombre responde
			# "applet not found".
			cp /bin/busybox $R/bin/busybox 2>/dev/null
			chmod 755 $R/bin/busybox 2>/dev/null
			if [ -x $R/bin/busybox ]; then
				echo "--- shell dentro de RouterOS ---"
				# chroot y no switch_root: si el shell sale, el init sigue
				# vivo (con switch_root, salir del shell mata al PID 1 y el
				# kernel hace panic). La consola se abre a mano porque el
				# stdin del init no siempre llega al proceso.
				chroot $R /bin/busybox sh -i \
					0</dev/console 1>/dev/console 2>&1
				echo "  shell terminado, sigue el arranque normal"
			else
				echo "  no he podido copiar busybox, sigo con sysinit"
			fi
		fi
		exec switch_root $R /sbin/sysinit start
	fi
	echo "  no se pudo montar el rootfs de RouterOS, sigo con el initramfs"
fi

[ -f /etc/network.conf ] && . /etc/network.conf
HOSTNAME=${HOSTNAME:-ed500}
STATIC_IP=${STATIC_IP:-192.168.1.2}
STATIC_MASK=${STATIC_MASK:-24}
STATIC_GW=${STATIC_GW:-192.168.1.1}
HTTP_PORT=${HTTP_PORT:-80}
hostname "$HOSTNAME"

mkdir -p /run /var/log
echo
echo "=================================================="
echo " $HOSTNAME - initramfs viva (kernel $(uname -r))"
echo "=================================================="
head -12 /proc/cpuinfo
echo

# --- esperar al switch ---
# El driver gswip va por detras: necesita el conduit y el reset del RCU, asi
# que la primera vez queda en probe diferido. Sin esta espera, el init corre
# antes de que existan los lan* y se queda sin red.
ifaces() {
	sed -n 's/^ *\([a-z0-9]*\):.*/\1/p' /proc/net/dev | grep -v '^lo$'
}

ESPERA=0
while [ "$ESPERA" -lt 30 ]; do
	HAY=0
	for n in $(ifaces); do
		case "$n" in lan*) HAY=1 ;; esac
	done
	[ "$HAY" = 1 ] && break
	ESPERA=$((ESPERA + 1))
	sleep 1
done
echo "espera de interfaces: ${ESPERA}s"

# --- red: puertos del switch en un bridge ---
# eth0/cbm0 es el maestro de DSA; puentearlo con sus propios puertos rompe el
# datapath. Por eso se prefieren los lan* y solo se cae en eth*/cbm* cuando no
# hay puertos DSA.
echo "interfaces:"
for n in $(ifaces); do
	echo "  $n $(cat /sys/class/net/$n/operstate 2>/dev/null)"
done

BRPORTS=""
for n in $(ifaces); do
	case "$n" in lan*) BRPORTS="$BRPORTS $n" ;; esac
done
if [ -z "$BRPORTS" ]; then
	for n in $(ifaces); do
		case "$n" in eth*|cbm*) BRPORTS="$BRPORTS $n" ;; esac
	done
fi

COUNT=0
for n in $BRPORTS; do COUNT=$((COUNT + 1)); done

if [ "$COUNT" -eq 0 ]; then
	echo "red: no hay interfaces (el driver Ethernet no ha creado ninguna)"
	echo "--- dmesg: switch / conduit / phy ---"
	dmesg 2>/dev/null | grep -iE "gswip|cbm|xrx|conduit|mdio|phy|dsa" | tail -25
	echo "--- dmesg: ultimas lineas ---"
	dmesg 2>/dev/null | tail -20
	iface=""
else
	echo "red: puertos:$BRPORTS"
	# El maestro de DSA (el conduit del SoC) tiene que estar arriba ANTES de
	# abrir los puertos: dsa_slave_open() devuelve -ENETDOWN si el maestro
	# esta down, y el ifconfig del puerto falla con "Network is down". El
	# maestro no se puentea con sus propios puertos.
	for m in cbm0 eth0; do
		if [ -d /sys/class/net/$m ]; then
			ifconfig "$m" up && echo "red: maestro $m up"
		fi
	done
	for n in $BRPORTS; do
		ifconfig "$n" up || echo "red: no he podido abrir $n"
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

# --- diagnostico del enlace -------------------------------------------
# Una foto del estado de los PHY y del switch. Va a la consola y a
# /www/enlace.txt: sin ella, un puerto caido no distingue entre "el PHY no
# ve cable" y "el driver no se entera del link".
diag_enlace() {
	echo "--- puertos ---"
	for m in cbm0 eth0; do
		[ -d /sys/class/net/$m ] || continue
		printf '  %-4s %-8s carrier=%-6s (maestro)\n' "$m" \
			"$(cat /sys/class/net/$m/operstate 2>/dev/null)" \
			"$(cat /sys/class/net/$m/carrier 2>/dev/null)"
	done
	for n in lan1 lan2 lan3 lan4; do
		[ -d /sys/class/net/$n ] || continue
		phy=$(readlink /sys/class/net/$n/phydev 2>/dev/null)
		printf '  %-4s %-8s carrier=%-6s phy=%s\n' "$n" \
			"$(cat /sys/class/net/$n/operstate 2>/dev/null)" \
			"$(cat /sys/class/net/$n/carrier 2>/dev/null)" \
			"${phy##*/}"
	done
	if [ -x /bin/phyreg ]; then
		for n in lan1 lan2 lan3 lan4; do
			[ -d /sys/class/net/$n ] || continue
			echo "  -- $n (BMCR BMSR ANAR 1000C 1000S) --"
			phyreg "$n" 0 1 4 9 10 2>&1 | sed 's/^/    /'
		done
	fi
	if [ -x /bin/swstats ] && [ -d /sys/class/net/lan1 ]; then
		echo "--- contadores del switch (lan1) ---"
		swstats lan1 2>&1 | sed 's/^/    /'
	fi
	echo "--- nand ---"
	if [ -r /proc/mtd ]; then
		sed 's/^/    /' /proc/mtd
	else
		echo "    sin /proc/mtd"
	fi
	ls -l /dev/mtd* 2>/dev/null | sed 's/^/    /'
	if [ -d /sys/class/net/lan1 ]; then
		echo "--- prueba de datapath: 3 pings al PC ---"
		[ -c /dev/mem ] || mknod /dev/mem c 1 1 2>/dev/null
		echo -n "    phyaddr lan1: "
		devmem 0x1c003d50 2>/dev/null
		if [ -x /bin/swstats ]; then
			swstats lan1 2>/dev/null | grep -E 'tx_packets|rx_packets|TxGoodPkts|TxDroppedPkts|RxGoodPkts' | sed 's/^/    antes: /'
		fi
		ping -c 3 -W 1 192.168.1.161 >/dev/null 2>&1
		if [ -x /bin/swstats ]; then
			swstats lan1 2>/dev/null | grep -E 'tx_packets|rx_packets|TxGoodPkts|TxDroppedPkts|RxGoodPkts' | sed 's/^/    despues: /'
		fi
	fi
	echo "--- dmesg: gswip / phy ---"
	dmesg 2>/dev/null | grep -iE 'gswip|xway|phy[0-9]|mii|link is|link up' | tail -20
}

sleep 6
{ echo "=== enlace tras 6 s ==="; diag_enlace; } > /www/enlace.txt 2>&1
cat /www/enlace.txt
(
	sleep 10
	echo
	echo "=== enlace tras 16 s ==="
	diag_enlace
) >> /www/enlace.txt 2>&1 &
(
	sleep 10
	diag_enlace
) &
[ -z "${CUR_IP:-}" ] && CUR_IP=$STATIC_IP

# --- servidores ---
mkdir -p /www/cgi-bin
if [ -x /bin/busybox ] || command -v httpd >/dev/null 2>&1; then
	httpd -p "$HTTP_PORT" -h /www 2>/dev/null && echo "web: http://$CUR_IP/"
fi
if command -v telnetd >/dev/null 2>&1; then
	telnetd -l /bin/sh 2>/dev/null && echo "telnet: puerto 23 (root, sin password)"
fi
if [ -x /usr/sbin/dropbear ]; then
	[ -f /etc/dropbear/dropbear_rsa_host_key ] || \
		/usr/sbin/dropbearkey -t rsa -f /etc/dropbear/dropbear_rsa_host_key >/dev/null 2>&1
	/usr/sbin/dropbear -R -p 22 2>/dev/null && echo "ssh: puerto 22 (root, sin password)"
fi

# --- log accesible por web (para cuando no hay consola) ---
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
echo "log del arranque: http://$CUR_IP/dmesg.txt"
echo "escribe 'exit' para reiniciar."
echo
setsid cttyhack /bin/sh 2>/dev/null || exec /bin/sh
