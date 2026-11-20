#!/bin/bash
C=/opt/ros-port/linux-5.6.3/.config
BB=/opt/ros-port/initramfs/bin/busybox

echo "===== DSA: tag protocol compilado? ====="
while read -r s; do
	[ -z "$s" ] && continue
	printf '%-32s ' "$s"
	grep -m1 "^$s=" "$C" 2>/dev/null || echo "NO"
done <<'EOF'
CONFIG_NET_DSA_TAG_GSWIP
CONFIG_NET_DSA_TAG_GSWIP3
CONFIG_NET_DSA_TAG_BRCM
EOF

echo
echo "===== CPS / timer / IRQ ====="
while read -r s; do
	[ -z "$s" ] && continue
	printf '%-32s ' "$s"
	grep -m1 "^$s=" "$C" 2>/dev/null || echo "NO"
done <<'EOF'
CONFIG_MIPS_CPS
CONFIG_MIPS_CM
CONFIG_MIPS_GIC
CONFIG_CEVT_GIC
CONFIG_IRQ_DOMAIN
CONFIG_MIPS_MACHINE
CONFIG_SMP
EOF

echo
echo "===== applets que usa el init ====="
while read -r a; do
	[ -z "$a" ] && continue
	printf '%-12s ' "$a"
	if strings "$BB" | grep -qx -- "$a"; then echo ok; else echo "FALTA"; fi
done <<'EOF'
mount
hostname
mknod
mkdir
ifconfig
route
brctl
udhcpc
httpd
telnetd
sleep
grep
sed
cut
head
tail
dmesg
setsid
cttyhack
echo
case
EOF

echo
echo "===== sintaxis del init (ash -n) ====="
if command -v busybox >/dev/null 2>&1; then
	busybox ash -n /opt/ros-port/initramfs/init && echo "sintaxis OK"
else
	sh -n /opt/ros-port/initramfs/init && echo "sintaxis OK (dash)"
fi
