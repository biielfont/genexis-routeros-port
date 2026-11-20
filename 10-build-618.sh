#!/bin/bash
#
# 10-build-618.sh - base 6.18 (la que tiene Ethernet funcionando en este SoC)
#
#   - arbol: /opt/ros-port/linux-6.18 (rama intel-mips-xrx500-v6.18 de grische)
#   - mete norrland.dts y lo enlaza como DTB embebido (el U-Boot de Genexis
#     no pasa DTB: pasa argc/argv)
#   - parchea prom.c para usar __dtb_start
#   - configura red + driver xRX500 + initramfs headless y compila
#
set -u

K=/opt/ros-port/linux-6.18
SRC=/mnt/c/Users/BFR/Documents/Genexis/routeros-port
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-
LOG=/opt/ros-port/build-618.log

echo "== 1. DTB norrland =="
cp "$SRC/tree/arch/mips/boot/dts/intel-mips/norrland-6.18.dts" "$K/arch/mips/boot/dts/intel-mips/norrland.dts"

python3 - <<'PY'
import os
K = "/opt/ros-port/linux-6.18"

# subdir del dts del SoC
p = f"{K}/arch/mips/boot/dts/Makefile"
s = open(p).read()
if "intel-mips" not in s:
    s += "subdir-$(CONFIG_INTEL_MIPS)\t+= intel-mips\n"
    open(p, "w").write(s)
    print("  dts/Makefile: subdir anadido")

# dtb enlazado
p = f"{K}/arch/mips/boot/dts/intel-mips/Makefile"
s = open(p).read()
if "norrland.dtb.o" not in s:
    s += "\nobj-y\t+= norrland.dtb.o\nalways\t:= norrland.dtb\n"
    open(p, "w").write(s)
    print("  dts/intel-mips/Makefile: norrland.dtb.o")

# prom.c: usar el dtb enlazado
p = f"{K}/arch/mips/intel-mips/prom.c"
s = open(p).read()
if "__dtb_start" not in s:
    s = s.replace("\tdtb = get_fdt();", "\tdtb = (void *)__dtb_start;")
    s = s.replace("static void plat_early_init_devtree(void)",
                  "extern char __dtb_start[];\n\nstatic void plat_early_init_devtree(void)")
    open(p, "w").write(s)
    print("  prom.c: usa __dtb_start")
PY

echo "== 2. config =="
cd "$K"
# El config del target de OpenWrt es un FRAGMENTO: se mezcla con una base
# completa (defconfig) o el kernel sale sin CONFIG_NET y sin drivers.
if [ ! -f /opt/ros-port/fragment-6.18 ]; then
	curl -sL "https://raw.githubusercontent.com/grische/openwrt/intel-mips-xrx500/target/linux/intel-mips/config-6.18" -o /opt/ros-port/fragment-6.18
fi
if [ ! -f .config.basemerge ]; then
	make ARCH=mips CROSS_COMPILE=$CROSS defconfig >/dev/null 2>&1
	cp .config /tmp/base.config
	scripts/kconfig/merge_config.sh -m /tmp/base.config /opt/ros-port/fragment-6.18 >/dev/null 2>&1
	touch .config.basemerge
fi
scripts/config \
	--enable NET --enable INET --enable PACKET --enable UNIX \
	--enable NETDEVICES --enable ETHERNET \
	--enable INTEL_XRX500_NET --enable INTEL_XRX500_BM --enable INTEL_XRX500_CBM_CONDUIT \
	--enable SERIAL_LANTIQ --enable SERIAL_EARLYCON --enable SERIAL_CORE_CONSOLE \
	--enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable BLK_DEV_INITRD \
	--set-str INITRAMFS_SOURCE /opt/ros-port/initramfs
make ARCH=mips CROSS_COMPILE=$CROSS olddefconfig >/dev/null 2>&1
grep -E "CONFIG_(INTEL_XRX500_NET|INTEL_XRX500_BM|ETHERNET|INITRAMFS_SOURCE)=" .config | sed 's/^/  /'

echo "== 3. build (vmlinux + dtb) =="
rm -f "$LOG"
{ make ARCH=mips CROSS_COMPILE=$CROSS -j4 vmlinux; echo "BUILD_EXIT=$?"; } >"$LOG" 2>&1
grep -E "error:|BUILD_EXIT" "$LOG" | tail -8
ls -l vmlinux arch/mips/boot/dts/intel-mips/norrland.dtb 2>/dev/null
