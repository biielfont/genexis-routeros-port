#!/bin/bash
# Compila el kernel 5.6.3 (el de RouterOS) con el driver GSWIP del XRX500
# y deja un uImage listo para TFTP.
set -u
T=/opt/ros-port/linux-5.6.3
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-
OUT="$(cd "$(dirname "$0")" && pwd)/out"
# Hay que resolver la ruta del script ANTES de entrar en el arbol del kernel;
# si se hace despues, dirname "./build-563.sh" apunta al kernel y no al proyecto.
AQUI=$(cd "$(dirname "$0")" && pwd)

cd "$T" || exit 1

# arreglos de arranque (idempotentes): gancho netfilter a NULL, bus del switch
# y reset del RCU visible en INTEL_MIPS
python3 "$AQUI/parche_arranque.py" || exit 1

# el init del initramfs se mantiene en el proyecto (una sola copia buena)
cp "$AQUI/init-initramfs.sh" /opt/ros-port/initramfs/init || {
  echo "init FALLO: no se pudo copiar al initramfs"
  exit 1
}
chmod 755 /opt/ros-port/initramfs/init || exit 1
# rootfs de RouterOS (squashfs extraido del npk oficial mipsbe)
if [ ! -s "$AQUI/ros/rootfs.squashfs" ]; then
  echo "rootfs FALLO: falta $AQUI/ros/rootfs.squashfs"
  exit 1
fi
cp "$AQUI/ros/rootfs.squashfs" /opt/ros-port/initramfs/ros.squashfs || {
  echo "rootfs FALLO: no se pudo copiar al initramfs"
  exit 1
}
echo "initramfs: rootfs de RouterOS incluido"

# herramienta de diagnostico del PHY (lee BMCR/BMSR por MDIO)
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/phyreg "$AQUI/phyreg.c" \
  || echo "phyreg FALLO"
# contadores RMON del switch (ETHTOOL_GSTATS)
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/swstats "$AQUI/swstats.c" \
  || echo "swstats FALLO"
# kbuild no sigue los cambios dentro del directorio: forzar el cpio nuevo
rm -f usr/initramfs_data.cpio usr/initramfs_data.cpio.gz usr/initramfs_data.o

scripts/config \
  --enable MULTIUSER \
  --enable FUTEX \
  --enable EPOLL \
  --enable EVENTFD \
  --enable SIGNALFD \
  --enable TIMERFD \
  --enable AIO \
  --enable POSIX_TIMERS \
  --enable ELF_CORE \
  --enable COREDUMP \
  --enable MISC_FILESYSTEMS \
  --enable NETFILTER \
  --enable NF_CONNTRACK \
  --enable RANDOM_TRUST_CPU \
  --enable POWER_RESET \
  --enable POWER_RESET_SYSCON \
  --enable SHMEM \
  --enable BLOCK \
  --enable IP_ADVANCED_ROUTER \
  --enable MIPS_FP_SUPPORT \
  --enable MTD \
  --enable MTD_BLOCK \
  --enable MTD_RAW_NAND \
  --enable MTD_NAND_CORE \
  --enable MTD_NAND_ECC_SW_HAMMING \
  --enable MTD_NAND_ECC_SW_BCH \
  --enable LZO_COMPRESS \
  --enable OVERLAY_FS \
  --enable MTD_NAND_LANTIQ_XRX500 \
  --enable MTD_OF_PARTS \
  --enable MTD_UBI \
  --enable MTD_UBI_BLOCK \
  --enable UBIFS_FS \
  --enable UBIFS_FS_ADVANCED_COMPR \
  --enable UBIFS_FS_LZO \
  --enable UBIFS_FS_ZLIB \
  --enable UBIFS_FS_ZSTD \
  --enable LZO_DECOMPRESS \
  --enable TMPFS \
  --enable SQUASHFS \
  --enable SQUASHFS_XZ \
  --enable BLK_DEV_LOOP \
  --enable INOTIFY_USER \
  --enable SYSVIPC \
  --enable FHANDLE \
  --enable IP_MULTIPLE_TABLES \
  --enable COMMON_CLK \
  --enable INTEL_CGU_CLK \
  --enable INTEL_GRX500_CGU_CLK \
  --enable BRIDGE \
  --enable TMPFS \
  --enable FW_LOADER \
  --enable BINFMT_SCRIPT \
  --enable RESET_CONTROLLER \
  --enable RESET_LANTIQ \
  --set-str EXTRA_FIRMWARE "lantiq/xrx500-phy-fw.bin" \
  --set-str EXTRA_FIRMWARE_DIR "/opt/ros-port/fw" \
  --enable SERIAL_LANTIQ \
  --enable SERIAL_CORE \
  --enable NET_DSA \
  --enable NET_DSA_TAG_GSWIP3 \
  --enable NET_DSA_XR_GSWIP \
  --enable NET_DSA_TAG_GSWIP \
  --enable PHYLINK \
  --enable INTEL_XRX500_NET \
  --enable INTEL_XRX500_BM \
  --enable INTEL_XRX500_CBM_CONDUIT \
  --enable INTEL_XWAY_PHY \
  --enable DEVMEM

if ! make ARCH=mips CROSS_COMPILE=$CROSS olddefconfig > /opt/olddef.log 2>&1; then
  echo "olddefconfig FALLO"
  tail -20 /opt/olddef.log
  exit 1
fi
echo "olddefconfig=0"

for s in CONFIG_BINFMT_SCRIPT CONFIG_RESET_CONTROLLER CONFIG_RESET_LANTIQ CONFIG_POWER_RESET CONFIG_POWER_RESET_SYSCON CONFIG_NET_DSA_TAG_GSWIP3 CONFIG_NET_DSA_TAG_GSWIP CONFIG_FUTEX CONFIG_EPOLL CONFIG_EVENTFD CONFIG_TIMERFD CONFIG_POSIX_TIMERS CONFIG_NETFILTER CONFIG_NF_CONNTRACK CONFIG_MULTIUSER CONFIG_BRIDGE CONFIG_SHMEM CONFIG_BLOCK CONFIG_IP_ADVANCED_ROUTER CONFIG_TMPFS CONFIG_SQUASHFS CONFIG_SQUASHFS_XZ CONFIG_BLK_DEV_LOOP CONFIG_INOTIFY_USER CONFIG_SYSVIPC CONFIG_FHANDLE CONFIG_IP_MULTIPLE_TABLES CONFIG_MIPS_FP_SUPPORT CONFIG_FW_LOADER CONFIG_EXTRA_FIRMWARE CONFIG_INTEL_GRX500_CGU_CLK CONFIG_SERIAL_LANTIQ CONFIG_NET_DSA CONFIG_NET_DSA_XR_GSWIP CONFIG_INTEL_XRX500_NET CONFIG_INTEL_XRX500_BM CONFIG_INTEL_XRX500_CBM_CONDUIT CONFIG_INTEL_XWAY_PHY CONFIG_MTD CONFIG_MTD_BLOCK CONFIG_MTD_RAW_NAND CONFIG_MTD_NAND_CORE CONFIG_MTD_NAND_ECC_SW_HAMMING CONFIG_MTD_NAND_ECC_SW_BCH CONFIG_MTD_NAND_LANTIQ_XRX500 CONFIG_MTD_OF_PARTS CONFIG_MTD_UBI CONFIG_MTD_UBI_BLOCK CONFIG_UBIFS_FS CONFIG_UBIFS_FS_ADVANCED_COMPR CONFIG_UBIFS_FS_LZO CONFIG_UBIFS_FS_ZLIB CONFIG_UBIFS_FS_ZSTD CONFIG_BCH CONFIG_LZO_DECOMPRESS CONFIG_DEVTMPFS; do
  if ! grep -q "^$s=" .config; then
    echo "CONFIG FALLO: $s"
    exit 1
  fi
  echo "$s -> $(grep "^$s=" .config)"
done

if ! grep -q '^CONFIG_INITRAMFS_SOURCE="/opt/ros-port/initramfs"' .config; then
  echo "CONFIG FALLO: INITRAMFS_SOURCE no apunta a /opt/ros-port/initramfs"
  exit 1
fi

echo "== compilando vmlinux =="
make ARCH=mips CROSS_COMPILE=$CROSS -j4 vmlinux > /opt/build563.log 2>&1
rc=$?
echo "build=$rc"
if [ "$rc" -ne 0 ]; then
  grep -E "error:|Error [0-9]" /opt/build563.log | head -8
  echo "build FALLO: no se genera uImage"
  exit 1
fi

if [ ! -s vmlinux ]; then
  echo "vmlinux FALLO: no existe o esta vacio"
  exit 1
fi

# El DTB va embebido en vmlinux: comprobar que es el de BCH-4/BBT/UBI y no
# uno viejo de una compilacion anterior.
DTB="$T/arch/mips/boot/dts/intel-mips/norrland.dtb"
if [ ! -s "$DTB" ]; then
  echo "DTB FALLO: no existe $DTB"
  exit 1
fi
if ! "$T/scripts/dtc/dtc" -I dtb -O dts "$DTB" 2>/dev/null | grep -q "nand-ecc-strength = <0x04>"; then
  echo "DTB FALLO: no tiene BCH-4"
  exit 1
fi
if ! "$T/scripts/dtc/dtc" -I dtb -O dts "$DTB" 2>/dev/null | grep -q "nand-on-flash-bbt"; then
  echo "DTB FALLO: no tiene nand-on-flash-bbt"
  exit 1
fi
if ! "$T/scripts/dtc/dtc" -I dtb -O dts "$DTB" 2>/dev/null | grep -q "ubi.mtd=ubi"; then
  echo "DTB FALLO: no tiene ubi.mtd=ubi"
  exit 1
fi
echo "dtb: BCH-4 + BBT + ubi.mtd=ubi"

ls -l vmlinux | awk '{print "vmlinux:", $5, "bytes"}'
ENTRY=$(${CROSS}readelf -h vmlinux | awk '/Entry point/{print $4}')
if [ -z "$ENTRY" ]; then
  echo "ENTRY FALLO: readelf no devolvio entry point"
  exit 1
fi
echo "entry=$ENTRY"
if ! ${CROSS}objcopy -O binary vmlinux /tmp/vmlinux.bin; then
  echo "objcopy FALLO"
  exit 1
fi
rm -f "$OUT/uImage-563"
if ! mkimage -A mips -O linux -T kernel -C none -a 0x80500000 -e "$ENTRY" \
        -n "Linux 5.6.3 ED500 (RouterOS base)" \
        -d /tmp/vmlinux.bin "$OUT/uImage-563" > /dev/null 2>&1; then
  echo "mkimage FALLO"
  exit 1
fi
if [ ! -s "$OUT/uImage-563" ]; then
  echo "uImage FALLO: no se creo"
  exit 1
fi
ls -l "$OUT/uImage-563" | awk '{print "uImage:", $5, "bytes"}'
