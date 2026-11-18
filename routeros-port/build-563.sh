#!/bin/bash
# Compila el kernel 5.6.3 (el de RouterOS) con el driver GSWIP del XRX500
# y deja un uImage listo para TFTP.
set -u
T=/opt/ros-port/linux-5.6.3
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-
OUT=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/out

cd "$T" || exit 1

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
  --set-str EXTRA_FIRMWARE "lantiq/xrx500-phy-fw.bin" \
  --set-str EXTRA_FIRMWARE_DIR "/opt/ros-port/fw" \
  --enable SERIAL_LANTIQ \
  --enable SERIAL_LANTIQ_CONSOLE \
  --enable SERIAL_CORE \
  --enable NET_DSA \
  --enable NET_DSA_TAG_GSWIP3 \
  --enable NET_DSA_XR_GSWIP \
  --enable NET_DSA_TAG_GSWIP \
  --enable PHYLINK \
  --enable INTEL_XRX500_NET \
  --enable INTEL_XRX500_BM \
  --enable INTEL_XRX500_CBM_CONDUIT

make ARCH=mips CROSS_COMPILE=$CROSS olddefconfig > /opt/olddef.log 2>&1
echo "olddefconfig=$?"

for s in CONFIG_POWER_RESET CONFIG_POWER_RESET_SYSCON CONFIG_NET_DSA_TAG_GSWIP3 CONFIG_NET_DSA_TAG_GSWIP CONFIG_FUTEX CONFIG_EPOLL CONFIG_EVENTFD CONFIG_TIMERFD CONFIG_POSIX_TIMERS CONFIG_NETFILTER CONFIG_NF_CONNTRACK CONFIG_MULTIUSER CONFIG_BRIDGE CONFIG_SHMEM CONFIG_BLOCK CONFIG_IP_ADVANCED_ROUTER CONFIG_TMPFS CONFIG_SQUASHFS CONFIG_SQUASHFS_XZ CONFIG_BLK_DEV_LOOP CONFIG_INOTIFY_USER CONFIG_SYSVIPC CONFIG_FHANDLE CONFIG_IP_MULTIPLE_TABLES CONFIG_MIPS_FP_SUPPORT CONFIG_FW_LOADER CONFIG_EXTRA_FIRMWARE CONFIG_INTEL_GRX500_CGU_CLK CONFIG_SERIAL_LANTIQ CONFIG_SERIAL_LANTIQ_CONSOLE CONFIG_NET_DSA CONFIG_NET_DSA_XR_GSWIP CONFIG_INTEL_XRX500_NET CONFIG_INTEL_XRX500_BM CONFIG_INTEL_XRX500_CBM_CONDUIT; do
  echo "$s -> $(grep "^$s=" .config || echo NO)"
done

echo "== compilando vmlinux =="
make ARCH=mips CROSS_COMPILE=$CROSS -j4 vmlinux > /opt/build563.log 2>&1
rc=$?
echo "build=$rc"
grep -E "error:|Error [0-9]" /opt/build563.log | head -8

if [ -f vmlinux ]; then
  ls -l vmlinux | awk '{print "vmlinux:", $5, "bytes"}'
  ENTRY=$(${CROSS}readelf -h vmlinux | awk '/Entry point/{print $4}')
  echo "entry=$ENTRY"
  ${CROSS}objcopy -O binary vmlinux /tmp/vmlinux.bin
  mkimage -A mips -O linux -T kernel -C none -a 0x80500000 -e "$ENTRY" \
          -n "Linux 5.6.3 ED500 (RouterOS base)" \
          -d /tmp/vmlinux.bin "$OUT/uImage-563" > /dev/null 2>&1
  if [ -f "$OUT/uImage-563" ]; then
    ls -l "$OUT/uImage-563" | awk '{print "uImage:", $5, "bytes"}'
  else
    echo "mkimage FALLO"
  fi
fi
