#!/bin/bash
#
# make-y3.sh - construye el .y3 instalable en NAND del ED500.
#
# El contenedor .y3 es cabecera de texto (1024 B) + imagen UBIFS + pkginfo +
# MD5. No lleva firma: el update de Genexis solo comprueba el MD5.
#
# La imagen UBIFS va al volumen rootfs_0 (480 LEBs, 0x3a20000 bytes) y lleva:
#   /boot/uImage        kernel 5.6.3 con el initramfs de RouterOS
#   /boot/norrland.dtb  DTB de la placa (SSO/LEDs/boton reset)
#   /boot/VERSION       identificacion
#   /rw/                configuracion persistente de RouterOS
#   /pad                relleno aleatorio para que la imagen llene el volumen
#
# El pad se borra en el primer arranque desde NAND (init-initramfs.sh), lo
# que deja ~30 MB libres para /flash/rw. U-Boot carga /boot/uImage y
# /boot/norrland.dtb con boot_ubi, sin TFTP.
#
# Uso:
#   tools/make-y3.sh [uImage] [dtb]
#
set -eu

AQUI=$(cd "$(dirname "$0")/.." && pwd)
IMG=${1:-$AQUI/out/uImage-563}
DTB=${2:-/opt/ros-port/linux-5.6.3/arch/mips/boot/dts/intel-mips/norrland.dtb}
OUT=$AQUI/out/ED500-routeros-7.17-nand.y3
UBIFS=$AQUI/out/rootfs-nand.ubifs
STAGE=$AQUI/out/y3-rootfs
STOCK=$AQUI/out/ED500-stock-original.y3
PAD_MB=${PAD_MB:-30}
MAX_LEBS=480

[ -s "$IMG" ] || { echo "make-y3: falta $IMG (ejecuta build-563.sh)" >&2; exit 1; }
[ -s "$DTB" ] || { echo "make-y3: falta $DTB" >&2; exit 1; }
command -v mkfs.ubifs >/dev/null || { echo "make-y3: falta mkfs.ubifs (mtd-utils)" >&2; exit 1; }

rm -rf "$STAGE" "$UBIFS" "$OUT"
mkdir -p "$STAGE/boot" "$STAGE/rw" "$STAGE/etc"

cp "$IMG" "$STAGE/boot/uImage"
cp "$DTB" "$STAGE/boot/norrland.dtb"
echo "ED500 RouterOS 7.17 (NAND)" > "$STAGE/boot/VERSION"
cat > "$STAGE/etc/os-release" <<'EOF'
NAME="ED500 RouterOS port"
VERSION="7.17"
ID=ed500
EOF

# Relleno incompresible: hace que la imagen UBIFS ocupe el volumen rootfs_0
# y deja sitio a /rw cuando el init lo borra en el primer arranque.
dd if=/dev/urandom of="$STAGE/pad" bs=1M count="$PAD_MB" status=none

# Geometria de la NAND MX30LF1G18AC y del volumen rootfs_0:
#   pagina/min I/O 2048, LEB 126976, maximo 480 LEBs.
mkfs.ubifs -m 2048 -e 126976 -c "$MAX_LEBS" -x zlib -r "$STAGE" -o "$UBIFS"

USZ=$(wc -c < "$UBIFS")
LEBS=$((USZ / 126976))
[ "$LEBS" -le "$MAX_LEBS" ] || {
	echo "make-y3: la UBIFS ocupa $LEBS LEBs > $MAX_LEBS" >&2
	exit 1
}
[ "$USZ" -le 60948480 ] || {
	echo "make-y3: la UBIFS ($USZ B) no cabe en rootfs_0 (60948480 B)" >&2
	exit 1
}

# pkginfo: se reutiliza el del firmware stock si esta disponible; si no,
# se genera una lista minima. yimage no lo usa para escribir la UBIFS.
PKG=$AQUI/out/pkginfo.txt
if [ -s "$STOCK" ]; then
	rm -rf /tmp/ed500-pkginfo
	python3 "$AQUI/08-y3tool.py" unpack "$STOCK" /tmp/ed500-pkginfo >/dev/null
	cp /tmp/ed500-pkginfo/pkginfo.txt "$PKG"
else
	cat > "$PKG" <<'EOF'
ED500 RouterOS 7.17 NAND
kernel 5.6.3
rootfs RouterOS 7.17 mipsbe
EOF
fi

python3 "$AQUI/08-y3tool.py" build "$OUT" \
	--ubifs "$UBIFS" --pkginfo "$PKG" \
	--release "GNX-4.3.6.999-R" --git 71b8d1b

# --- comprobaciones del contenedor y del contenido ---
echo "--- verificacion ---"
python3 "$AQUI/08-y3tool.py" info "$OUT" | tee /tmp/ed500-y3-info.txt
grep -q 'COINCIDE' /tmp/ed500-y3-info.txt || { echo "make-y3: MD5 no coincide" >&2; exit 1; }
grep -q 'magia 31181006' /tmp/ed500-y3-info.txt || { echo "make-y3: UBIFS sin magia" >&2; exit 1; }

if command -v ubireader_display_info >/dev/null 2>&1; then
	ubireader_display_info "$UBIFS" 2>/dev/null | grep -E 'leb_cnt|max_leb_cnt|min_io_size|leb_size' | sed 's/^/  /'
fi

# Extraer y comparar el kernel/DTB que realmente van dentro del .y3.
if command -v ubireader_extract_files >/dev/null 2>&1; then
	rm -rf /tmp/ed500-y3tree
	ubireader_extract_files -o /tmp/ed500-y3tree "$UBIFS" >/dev/null 2>&1
	Y3IMG=$(find /tmp/ed500-y3tree -path '*/boot/uImage' | head -1)
	Y3DTB=$(find /tmp/ed500-y3tree -path '*/boot/norrland.dtb' | head -1)
	[ -n "$Y3IMG" ] && cmp -s "$Y3IMG" "$IMG" || { echo "make-y3: uImage dentro del .y3 no coincide" >&2; exit 1; }
	[ -n "$Y3DTB" ] && cmp -s "$Y3DTB" "$DTB" || { echo "make-y3: DTB dentro del .y3 no coincide" >&2; exit 1; }
	echo "  /boot/uImage y /boot/norrland.dtb coinciden byte a byte"
fi

echo "make-y3: $OUT"
echo "  UBIFS $USZ B, $LEBS LEBs (max $MAX_LEBS), pad ${PAD_MB} MB"
echo "  MD5 $(md5sum "$OUT" | awk '{print $1}')"
echo "  instalacion U-Boot: tftpboot 0x80800000 last.y3; run update_image; reset"
