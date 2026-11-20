#!/bin/bash
# H1: compilar el kernel GPL de MikroTik (linux-5.6.3 + parche) para MIPS.
# Toolchain: Bootlin mips32 glibc (Kali no empaqueta gcc-mips-linux-gnu).
set -uo pipefail

export DEBIAN_FRONTEND=noninteractive
WORK=/opt/ros-port
TC=/opt/toolchain
LOG=$WORK/build.log
mkdir -p "$WORK" "$TC"
exec > >(tee -a "$LOG") 2>&1

echo "=== $(date -u) H1 start ==="

apt-get update -y
apt-get install -y --no-install-recommends \
    make bc flex bison libssl-dev libelf-dev xz-utils patch wget ca-certificates
echo "APT_EXIT=$?"

if [ ! -x "$TC/bin/mips-buildroot-linux-gnu-gcc" ]; then
    cd "$TC" || exit 1
    URL=https://toolchains.bootlin.com/downloads/releases/toolchains/mips32/tarballs/mips32--glibc--stable-2024.05-1.tar.xz
    wget -q -O tc.tar.xz "$URL" || { echo "TC_DOWNLOAD_FAIL"; exit 1; }
    tar xf tc.tar.xz || { echo "TC_TAR_FAIL"; exit 1; }
    mv mips32--glibc--stable-2024.05-1/* "$TC"/ 2>/dev/null
fi
"$TC/bin/mips-buildroot-linux-gnu-gcc" --version | head -1
CROSS=$TC/bin/mips-buildroot-linux-gnu-
ls "${CROSS}gcc" >/dev/null || { echo "TOOLCHAIN_MISSING"; exit 1; }

cd "$WORK" || exit 1
[ -f linux-5.6.3.tar.xz ] || wget -q https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.6.3.tar.xz
[ -f linux-5.6.3.patch ]  || wget -q https://raw.githubusercontent.com/tikoci/mikrotik-gpl/main/2025-03-19/linux-5.6.3.patch
[ -f mips.config ]         || wget -q https://raw.githubusercontent.com/tikoci/mikrotik-gpl/main/2025-03-19/configs/mips.config
ls -l linux-5.6.3.tar.xz linux-5.6.3.patch mips.config

rm -rf linux-5.6.3
tar xf linux-5.6.3.tar.xz || { echo "TAR_FAIL"; exit 1; }
cd linux-5.6.3 || exit 1

echo "=== apply MikroTik patch ==="
patch -p1 --batch --forward < ../linux-5.6.3.patch > ../patch.out 2>&1
echo "PATCH_EXIT=$?"
tail -15 ../patch.out
find . -name '*.rej' | head -10

cp ../mips.config .config
echo "=== olddefconfig ==="
make ARCH=mips CROSS_COMPILE="$CROSS" olddefconfig
echo "OLDDEFCONFIG_EXIT=$?"
grep -E "^CONFIG_MIPS_MIKROTIK|^CONFIG_CPU_MIPS32_R2|^CONFIG_CPU_MIPS32=" .config | head -5

echo "=== build vmlinux ==="
make ARCH=mips CROSS_COMPILE="$CROSS" -j"$(nproc)" vmlinux
echo "BUILD_EXIT=$?"
ls -l vmlinux 2>/dev/null && file vmlinux && echo "BUILD_OK" || echo "BUILD_FAILED"
echo "=== $(date -u) H1 end ==="
