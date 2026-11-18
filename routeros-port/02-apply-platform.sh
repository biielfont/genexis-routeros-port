#!/bin/bash
# H2a: meter la plataforma intel-mips (xRX500/GRX350) en el arbol 5.6.3 y preparar config.
set -euo pipefail

KDIR=/opt/ros-port/linux-5.6.3
SRC=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/tree

echo "== copiando plataforma =="
mkdir -p "$KDIR/arch/mips/intel-mips" "$KDIR/arch/mips/include/asm/mach-intel-mips"
cp -f "$SRC"/arch/mips/intel-mips/* "$KDIR/arch/mips/intel-mips/"
cp -f "$SRC"/arch/mips/include/asm/mach-intel-mips/* "$KDIR/arch/mips/include/asm/mach-intel-mips/"

echo "== Kbuild.platforms =="
python3 - <<'PY'
p='/opt/ros-port/linux-5.6.3/arch/mips/Kbuild.platforms'
s=open(p).read()
if 'intel-mips/' not in s:
    s=s.replace('platform-$(CONFIG_MIPS_GENERIC)\t\t+= generic/',
                'platform-$(CONFIG_MIPS_GENERIC)\t\t+= generic/\nplatform-$(CONFIG_INTEL_MIPS)\t\t+= intel-mips/')
    open(p,'w').write(s)
print(open(p).read())
PY

echo "== Kconfig =="
python3 - <<'PY'
p='/opt/ros-port/linux-5.6.3/arch/mips/Kconfig'
s=open(p).read()
block='''config INTEL_MIPS
	bool "Intel MIPS interAptiv SoC based platforms"
	select BOOT_RAW
	select CEVT_R4K
	select COMMON_CLK
	select CPU_MIPS32_3_5_EVA
	select CPU_MIPS32_3_5_FEATURES
	select CPU_MIPSR2_IRQ_EI
	select CPU_MIPSR2_IRQ_VI
	select CSRC_R4K
	select DMA_NONCOHERENT
	select GENERIC_ISA_DMA
	select IRQ_MIPS_CPU
	select MFD_CORE
	select MFD_SYSCON
	select MIPS_CPU_SCACHE
	select MIPS_GIC
	select SYS_HAS_CPU_MIPS32_R2
	select SYS_SUPPORTS_BIG_ENDIAN
	select SYS_SUPPORTS_32BIT_KERNEL
	select SYS_SUPPORTS_MIPS_CPS
	select SYS_SUPPORTS_MULTITHREADING
	select TIMER_OF
	select USE_OF

'''
if 'config INTEL_MIPS' not in s:
    s = s.replace('config MACH_LOONGSON32', block + 'config MACH_LOONGSON32', 1)
if 'arch/mips/intel-mips/Kconfig' not in s:
    s = s.replace('source "arch/mips/lantiq/Kconfig"',
                  'source "arch/mips/intel-mips/Kconfig"\nsource "arch/mips/lantiq/Kconfig"', 1)
open(p,'w').write(s)
print("Kconfig OK")
PY
grep -n "INTEL_MIPS\|intel-mips/Kconfig" "$KDIR"/arch/mips/Kconfig | head || true

echo "== config minima =="
cd "$KDIR"
make ARCH=mips CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- allnoconfig > /tmp/cfg.log 2>&1
./scripts/config --file .config \
  --enable INTEL_MIPS --enable MIPS_GIC --enable USE_OF --enable COMMON_CLK \
  --enable SERIAL_LANTIQ --enable TTY --enable PRINTK --enable BLK_DEV_INITRD \
  --enable RD_GZIP --enable BINFMT_ELF --enable ELF_CORE --enable PROC_FS --enable SYSFS \
  --enable MODULES --enable MODULE_UNLOAD --enable KALLSYMS
make ARCH=mips CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- olddefconfig >> /tmp/cfg.log 2>&1
echo "cfg_exit=$?"
grep -E "^CONFIG_(INTEL_MIPS|MIPS_GIC|MIPS_CPS|CPU_MIPS32_3_5_EVA|EVA|SERIAL_LANTIQ|USE_OF|MIPS)=|^# CONFIG_INTEL_MIPS" .config | head -10 || true
