#!/bin/bash
# Auditoria previa al primer arranque del 5.6.3 en el ED500.
C=/opt/ros-port/linux-5.6.3/.config

echo "===== opciones del kernel ====="
for s in CONFIG_BRIDGE \
         CONFIG_EXTRA_FIRMWARE \
         CONFIG_EXTRA_FIRMWARE_DIR \
         CONFIG_DEVTMPFS \
         CONFIG_DEVTMPFS_MOUNT \
         CONFIG_TMPFS \
         CONFIG_INET \
         CONFIG_PACKET \
         CONFIG_UNIX \
         CONFIG_SERIAL_EARLYCON \
         CONFIG_MTD_UBI \
         CONFIG_BLK_DEV_INITRD \
         CONFIG_SERIAL_LANTIQ \
         CONFIG_PROC_FS \
         CONFIG_SYSFS ; do
	printf '%-28s ' "$s"
	grep -m1 "^$s=" "$C" >/dev/null 2>&1 && grep -m1 "^$s=" "$C" || echo "NO"
done

echo
echo "===== initramfs: contenido ====="
ls /opt/ros-port/initramfs/bin /opt/ros-port/initramfs/sbin 2>/dev/null | head -20

echo
echo "===== initramfs: tamano total ====="
du -sh /opt/ros-port/initramfs 2>/dev/null

echo
echo "===== busybox del initramfs: applets clave ====="
BB=$(find /opt/ros-port/initramfs -name busybox -type f | head -1)
echo "busybox: $BB"
if [ -n "$BB" ]; then
	for a in brctl ip udhcpc httpd telnetd sh; do
		printf '%-8s ' "$a"
		if strings "$BB" 2>/dev/null | grep -qx "$a"; then echo ok; else echo FALTA; fi
	done
	file "$BB" 2>/dev/null
fi

echo
echo "===== firmware GPHY ====="
find /opt/ros-port -name "xrx500-phy-fw.bin" 2>/dev/null | head -3
grep -rn "xrx500-phy-fw" /opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/*.c 2>/dev/null | head -3
