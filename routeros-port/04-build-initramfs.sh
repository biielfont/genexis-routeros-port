#!/bin/bash
#
# 04-build-initramfs.sh - DTS + initramfs headless + kernel arrancable
#
#   - integra norrland.dts en arch/mips/boot/dts/intel-mips/
#   - compila busybox estatico (MIPS BE) con red, httpd y telnetd
#   - compila dropbear estatico (SSH) si se puede descargar
#   - crea un initramfs que levanta red, sirve una pagina de estado con logs
#   - activa DTB integrado + serial lantiq + initramfs y compila vmlinux + dtb
#
set -u

K=/opt/ros-port/linux-5.6.3
SRC=/mnt/c/Users/BFR/Documents/Genexis/routeros-port
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-
LOG=/opt/ros-port/build5.log
BBVER=1.36.1
BB=/opt/ros-port/busybox-$BBVER
DBVER=2022.83
DB=/opt/ros-port/dropbear-$DBVER
INITRD=/opt/ros-port/initramfs

echo "== 1. DTS =="
mkdir -p "$K/arch/mips/boot/dts/intel-mips"
cp "$SRC/tree/arch/mips/boot/dts/intel-mips/norrland.dts" "$K/arch/mips/boot/dts/intel-mips/"
cp "$SRC/tree/arch/mips/boot/dts/intel-mips/Makefile"      "$K/arch/mips/boot/dts/intel-mips/"

python3 - "$K/arch/mips/boot/dts/Makefile" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
if 'intel-mips' not in s:
    s = s.replace("subdir-y\t+= rb\n", "subdir-y\t+= rb\nsubdir-y\t+= intel-mips\n")
    open(p, 'w').write(s)
    print("boot/dts/Makefile: intel-mips anadido")
else:
    print("boot/dts/Makefile: ya estaba")
PY

echo "== 2. busybox =="
if [ ! -x "$BB/busybox" ]; then
  cd /opt/ros-port
  [ -f busybox-$BBVER.tar.bz2 ] || \
    wget -q https://busybox.net/downloads/busybox-$BBVER.tar.bz2 || \
    wget -q https://cdn.busybox.net/downloads/busybox-$BBVER.tar.bz2
  command -v bzip2 >/dev/null || apt-get install -y bzip2 >/dev/null 2>&1
  tar xjf busybox-$BBVER.tar.bz2
  cd "$BB"
  make ARCH=mips CROSS_COMPILE=$CROSS defconfig >/dev/null 2>&1
  sed -i 's/^# CONFIG_STATIC is not set/CONFIG_STATIC=y/' .config
  sed -i 's/^CONFIG_TC=y/# CONFIG_TC is not set/' .config
  make ARCH=mips CROSS_COMPILE=$CROSS oldconfig >/dev/null 2>&1
fi
# red + servidores en la busybox
for o in HTTPD TELNETD UDHCPC IP IFCONFIG WGET NC NETSTAT TOP; do
  sed -i "s/^# CONFIG_${o} is not set/CONFIG_${o}=y/" "$BB/.config"
done
make -C "$BB" ARCH=mips CROSS_COMPILE=$CROSS oldconfig >/dev/null 2>&1
make -C "$BB" ARCH=mips CROSS_COMPILE=$CROSS -j4 >/opt/ros-port/busybox-build.log 2>&1
echo "busybox rc=$?"

echo "== 3. dropbear (SSH, opcional) =="
if [ ! -x "$DB/dropbear" ]; then
  cd /opt/ros-port
  [ -f dropbear-$DBVER.tar.bz2 ] || \
    wget -q "https://matt.ucc.asn.au/dropbear/releases/dropbear-$DBVER.tar.bz2" 2>/dev/null || true
  if [ -f dropbear-$DBVER.tar.bz2 ]; then
    tar xjf dropbear-$DBVER.tar.bz2 2>/dev/null
    cd "$DB"
    PATH=/opt/toolchain/bin:$PATH ./configure --host=mips-buildroot-linux-gnu \
      --disable-zlib --disable-utmpx --disable-wtmp \
      CFLAGS="-Os -static" LDFLAGS="-static" >/dev/null 2>&1
    PATH=/opt/toolchain/bin:$PATH make PROGRAMS="dropbear dropbearkey" -j4 >/tmp/db.log 2>&1
    echo "dropbear rc=$?"
  else
    echo "  no se pudo descargar dropbear; se sigue solo con telnetd"
  fi
fi

echo "== 4. initramfs =="
rm -rf "$INITRD"
mkdir -p "$INITRD"/{bin,sbin,etc,proc,sys,dev,tmp,root,usr/bin,usr/sbin,www/cgi-bin,etc/dropbear}
make -C "$BB" ARCH=mips CROSS_COMPILE=$CROSS CONFIG_PREFIX="$INITRD" install >/dev/null 2>&1
echo "busybox install rc=$?"
if [ -x "$DB/dropbear" ]; then
  cp "$DB/dropbear" "$DB/dropbearkey" "$INITRD"/usr/sbin/ 2>/dev/null && echo "  dropbear incluido"
fi

cat > "$INITRD/etc/network.conf" <<'EOF'
# Red del sistema de rescate: DHCP primero, si no hay, esta IP fija.
HOSTNAME=ed500
STATIC_IP=192.168.1.2
STATIC_MASK=24
STATIC_GW=192.168.1.1
HTTP_PORT=80
EOF

cat > "$INITRD/init" <<'EOF'
#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

mount -t proc     proc     /proc
mount -t sysfs    sysfs    /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null
[ -c /dev/console ] || mknod /dev/console c 5 1 2>/dev/null

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
cat /proc/cpuinfo | head -12
echo

# --- red: primero DHCP, si no, IP fija ---
iface=""
for d in /sys/class/net/*; do
	n=$(basename "$d")
	[ "$n" = "lo" ] && continue
	iface=$n
	break
done
ip link set lo up 2>/dev/null

if [ -z "$iface" ]; then
	echo "red: no hay interfaces (falta el driver Ethernet de este SoC)"
else
	echo "red: usando $iface"
	ip link set "$iface" up 2>/dev/null
	if command -v udhcpc >/dev/null 2>&1; then
		udhcpc -i "$iface" -t 3 -T 2 -n -q >/tmp/dhcp.log 2>&1
	fi
	if ! ip -4 addr show "$iface" 2>/dev/null | grep -q "inet "; then
		echo "red: sin DHCP, IP fija $STATIC_IP/$STATIC_MASK"
		ip addr add "$STATIC_IP/$STATIC_MASK" dev "$iface" 2>/dev/null
		[ -n "$STATIC_GW" ] && ip route add default via "$STATIC_GW" 2>/dev/null
	fi
	CUR_IP=$(ip -4 addr show "$iface" | awk '/inet /{print $2}' | cut -d/ -f1)
echo "red: ${CUR_IP:-sin ip} en $iface"
fi
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

echo
echo "estado: http://$CUR_IP/   ·   consola: ttyLTQ0"
echo "escribe 'exit' para reiniciar."
echo
setsid cttyhack /bin/sh 2>/dev/null || exec /bin/sh
EOF
chmod +x "$INITRD/init"

# pagina de estado + CGI con los logs
cat > "$INITRD/www/index.html" <<'EOF'
<!doctype html>
<html><head><meta charset="utf-8"><title>ED500</title>
<style>body{font:13px/1.45 monospace;background:#111;color:#ddd;margin:1.5em}
pre{white-space:pre-wrap}h1{font-size:15px;color:#6c6}
a{color:#6cf}</style></head>
<body>
<h1>Genexis Pure ED500 - GRX350 (kernel 5.6.3 portado)</h1>
<div id="st">cargando...</div>
<script>
async function tick(){
  try{const r=await fetch('/cgi-bin/status');document.getElementById('st').innerHTML='<pre>'+await r.text()+'</pre>';}
  catch(e){document.getElementById('st').innerHTML='<pre>sin respuesta: '+e+'</pre>';}
}
tick();setInterval(tick,5000);
</script>
</body></html>
EOF

# udhcpc necesita su script para aplicar la concesion
mkdir -p "$INITRD/usr/share/udhcpc"
cat > "$INITRD/usr/share/udhcpc/default.script" <<'EOF'
#!/bin/sh
case "$1" in
  deconfig)
    ip addr flush dev "$interface" 2>/dev/null
    ip link set "$interface" up 2>/dev/null
    ;;
  bound|renew)
    ip addr flush dev "$interface" 2>/dev/null
    ip addr add "$ip/$mask" dev "$interface" 2>/dev/null
    [ -n "$router" ] && for r in $router; do ip route add default via "$r" dev "$interface" 2>/dev/null; done
    if [ -n "$dns" ]; then : > /etc/resolv.conf; for d in $dns; do echo "nameserver $d" >> /etc/resolv.conf; done; fi
    ;;
esac
exit 0
EOF
chmod +x "$INITRD/usr/share/udhcpc/default.script"

cat > "$INITRD/www/cgi-bin/status" <<'EOF'
#!/bin/sh
echo "Content-Type: text/plain"
echo
echo "=== ESTADO ==="
echo "host      : $(hostname)"
echo "kernel    : $(uname -srm)"
echo "uptime    : $(uptime | sed 's/^ *//')"
echo "fecha     : $(date)"
echo
echo "--- comprobaciones ---"
grep -q "Linux version" /proc/version && echo "[ok] kernel en ejecucion"
[ -d /proc/sys ] && echo "[ok] proc montado"
[ "$(ls /sys/devices/system/cpu 2>/dev/null | grep -c '^cpu[0-9]')" -ge 1 ] && echo "[ok] cpus detectadas"
grep -qi "interAptiv\|MIPS" /proc/cpuinfo && echo "[ok] cpu mips: $(grep -m1 'cpu model' /proc/cpuinfo | cut -d: -f2)"
sw=$(awk '/MemTotal/{print $2}' /proc/meminfo); [ -n "$sw" ] && echo "[ok] memoria: $((sw/1024)) MiB"
for d in /sys/class/net/*; do
	n=$(basename "$d")
	case "$n" in lo|sit0|ip6tnl0|tunl0) continue;; esac
	a=$(ip -4 addr show "$n" 2>/dev/null | awk '/inet /{print $2}')
	[ -n "$a" ] && echo "[ok] red $n $a" || echo "[--] $n sin ip"
done
echo
echo "--- memoria ---"; head -4 /proc/meminfo
echo
echo "--- interfaces ---"; ip -4 addr show 2>/dev/null | grep -E "^[0-9]|inet "
echo
echo "--- dmesg (ultimas 60 lineas) ---"
dmesg | tail -60
EOF
chmod +x "$INITRD/www/cgi-bin/status"

mknod -m 600 "$INITRD/dev/console" c 5 1 2>/dev/null || true
mknod -m 666 "$INITRD/dev/null"    c 1 3 2>/dev/null || true
mknod -m 660 "$INITRD/dev/ttyS0"   c 4 64 2>/dev/null || true
mknod -m 660 "$INITRD/dev/ttyLTQ0" c 4 64 2>/dev/null || true
ln -sf busybox "$INITRD/bin/sh"
ln -sf ../bin/busybox "$INITRD/sbin/init" 2>/dev/null || true
du -sh "$INITRD"

echo "== 5. config del kernel =="
cd "$K"
S=scripts/config
$S --enable DTB_INTEL_MIPS_GRX500 \
   --enable SERIAL_LANTIQ --enable SERIAL_EARLYCON --enable SERIAL_CORE_CONSOLE \
   --enable TTY --enable VT --enable PRINTK \
   --enable DEVTMPFS --enable DEVTMPFS_MOUNT \
   --enable NET --enable INET --enable UNIX --enable PACKET --enable INET_DIAG \
   --enable IP_PNP --disable NET_RX_BUSY_POLL \
   --set-str INITRAMFS_SOURCE "$INITRD" \
   --enable BLK_DEV_INITRD
make ARCH=mips CROSS_COMPILE=$CROSS olddefconfig >/dev/null 2>&1
grep -E "CONFIG_(DTB_INTEL_MIPS_GRX500|BUILTIN_DTB|SERIAL_LANTIQ|NET|INET|INITRAMFS_SOURCE)=" .config | sed 's/^/  /'

echo "== 6. build =="
rm -f "$LOG"
{ make ARCH=mips CROSS_COMPILE=$CROSS -j4 vmlinux; echo "BUILD_EXIT=$?"; } >"$LOG" 2>&1
grep -E "error:|BUILD_EXIT" "$LOG" | tail -5
ls -l vmlinux arch/mips/boot/dts/intel-mips/norrland.dtb 2>/dev/null
