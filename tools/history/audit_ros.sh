#!/bin/bash
# Opciones de kernel que el rootfs/userspace de RouterOS necesita.
C=/opt/ros-port/linux-5.6.3/.config

echo "===== kernel: lo que RouterOS espera ====="
while read -r s; do
	[ -z "$s" ] && continue
	printf '%-28s ' "$s"
	grep -m1 "^$s=" "$C" 2>/dev/null || echo "NO"
done <<'EOF'
CONFIG_MODULES
CONFIG_MODULE_UNLOAD
CONFIG_MODVERSIONS
CONFIG_MODULE_SIG
CONFIG_MODULE_SIG_FORCE
CONFIG_SQUASHFS
CONFIG_SQUASHFS_XZ
CONFIG_MIPS_FP_SUPPORT
CONFIG_UNIX98_PTYS
CONFIG_DEVPTS_MULTIPLE_INSTANCES
CONFIG_TMPFS
CONFIG_BLK_DEV_LOOP
CONFIG_BLK_DEV_RAM
CONFIG_NET_NS
CONFIG_IP_MULTIPLE_TABLES
CONFIG_INET_DIAG
CONFIG_PACKET_DIAG
CONFIG_UNIX_DIAG
CONFIG_INET_UDP_DIAG
CONFIG_ELF_CORE
CONFIG_BINFMT_ELF
CONFIG_BINFMT_MISC
CONFIG_PRINTK
CONFIG_SYSVIPC
CONFIG_FHANDLE
CONFIG_INOTIFY_USER
EOF

echo
echo "===== version y release ====="
cat /opt/ros-port/linux-5.6.3/include/generated/utsrelease.h 2>/dev/null
grep -E "^CONFIG_LOCALVERSION|^CONFIG_SMP|^CONFIG_PREEMPT" "$C" 2>/dev/null

echo
echo "===== npk de RouterOS por el disco ====="
ls -l /mnt/c/Users/BFR/Downloads/*.npk 2>/dev/null | head -5
ls -l /mnt/c/Users/BFR/Documents/Genexis/*.npk 2>/dev/null | head -5
