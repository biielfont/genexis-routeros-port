#!/bin/bash
#
# build-fwenv.sh - compila fw_printenv/fw_setenv estaticos para MIPS BE.
#
# El firmware stock de Genexis resetea el flag de arranque de U-Boot desde
# /etc/init.d/bootcount con fw_setenv. Para que un arranque desde NAND no
# vuelva al banco stock tras varios reinicios, el initramfs necesita las
# mismas herramientas. Se compilan desde las fuentes de U-Boot que ya estan
# en el equipo (tools/env) con la toolchain de /opt.
#
# Uso:
#   tools/build-fwenv.sh [destino-initramfs]
#
set -eu

AQUI=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:-/opt/ros-port/initramfs}
UBOOT_SRC=${UBOOT_SRC:-/opt/qemu-9.2.0/roms/u-boot}
CROSS=${CROSS:-/opt/toolchain/bin/mips-buildroot-linux-gnu-}
BUILD=${BUILD:-/tmp/ed500-fwenv}

[ -d "$UBOOT_SRC/tools/env" ] || {
	echo "fwenv: falta $UBOOT_SRC/tools/env (define UBOOT_SRC)" >&2
	exit 1
}
[ -x "${CROSS}gcc" ] || {
	echo "fwenv: falta ${CROSS}gcc" >&2
	exit 1
}

mkdir -p "$BUILD/generated" "$DEST/usr/sbin" "$DEST/etc"
: > "$BUILD/generated/autoconf.h"
: > "$BUILD/config.h"
cat > "$BUILD/version.h" <<'EOF'
#define PLAIN_VERSION "ed500"
#define U_BOOT_VERSION "ed500"
EOF

# Los includes de U-Boot van con -idirafter: si van con -I, su stdio.h
# sustituye al de la libc y la compilacion falla.
"${CROSS}gcc" -static -O2 -DUSE_HOSTCC -DTEXT_BASE=0 \
	-DCONFIG_FILE='"/etc/fw_env.config"' \
	-I"$BUILD" -I"$UBOOT_SRC/tools" -I"$UBOOT_SRC/tools/env" \
	-idirafter "$UBOOT_SRC/include" -idirafter "$UBOOT_SRC/arch/mips/include" \
	-o "$BUILD/fw_printenv" \
	"$UBOOT_SRC/tools/env/fw_env_main.c" \
	"$UBOOT_SRC/tools/env/fw_env.c" \
	"$UBOOT_SRC/tools/env/crc32.c" \
	"$UBOOT_SRC/tools/env/ctype.c" \
	"$UBOOT_SRC/tools/env/linux_string.c" \
	"$UBOOT_SRC/tools/env/env_attr.c" \
	"$UBOOT_SRC/tools/env/env_flags.c"

# Tiene que ser estatico y big-endian: el initramfs no lleva libc dinamica
# y RouterOS es MIPS BE.
if "${CROSS}readelf" -d "$BUILD/fw_printenv" 2>/dev/null | grep -q NEEDED; then
	echo "fwenv: el binario no es estatico" >&2
	exit 1
fi
if ! "${CROSS}readelf" -h "$BUILD/fw_printenv" | grep -q 'big endian'; then
	echo "fwenv: el binario no es big-endian" >&2
	exit 1
fi

# Se copia dos veces, no un symlink: el generador de initramfs del kernel
# no siempre conserva enlaces y el init necesita /usr/sbin/fw_setenv real.
cp "$BUILD/fw_printenv" "$DEST/usr/sbin/fw_printenv"
cp "$BUILD/fw_printenv" "$DEST/usr/sbin/fw_setenv"
chmod 755 "$DEST/usr/sbin/fw_printenv" "$DEST/usr/sbin/fw_setenv"

# El firmware stock guarda el entorno en los volumenes UBI env1/env2.
cat > "$DEST/etc/fw_env.config" <<'EOF'
# U-Boot environment del ED500 (Genexis): dos copias redundantes en UBI.
/dev/ubi0:env1 0x0 0x1f000
/dev/ubi0:env2 0x0 0x1f000
EOF

echo "fwenv: $(wc -c < "$BUILD/fw_printenv") bytes -> $DEST/usr/sbin/fw_printenv"
