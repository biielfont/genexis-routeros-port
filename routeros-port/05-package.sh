#!/bin/bash
#
# 05-package.sh - genera los artefactos de arranque en out/
#
set -eu

K=/opt/ros-port/linux-5.6.3
OUT=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/out
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-

[ -f "$K/vmlinux" ] || { echo "falta $K/vmlinux: ejecuta antes 04-build-initramfs.sh"; exit 1; }
mkdir -p "$OUT"

"$CROSS"objcopy -O binary "$K/vmlinux" "$OUT/vmlinux.bin"
gzip -9 -c -f "$OUT/vmlinux.bin" > "$OUT/vmlinux.bin.gz"
mkimage -A mips -O linux -T kernel -C none \
	-a 0x80500000 -e 0x80500000 \
	-n "GRX350 norrland 5.6.3" \
	-d "$OUT/vmlinux.bin" "$OUT/uImage" >/dev/null

cp "$K/vmlinux" "$OUT/vmlinux.elf"
cp "$K/arch/mips/boot/dts/intel-mips/norrland.dtb" "$OUT/"

echo "artefactos en $OUT"
ls -l "$OUT"
sha256sum "$OUT"/uImage "$OUT"/vmlinux.elf | sed 's/^/  /'

# --- invariantes de la imagen (lo que U-Boot y el kernel esperan) ---
echo
echo "verificacion de la imagen:"
fail=0
expect() { # valor esperado, obtenido, descripcion
	if [ "$1" = "$2" ]; then
		echo "  OK    $3"
	else
		echo "  FALLO $3 (esperado '$1', obtenido '$2')"
		fail=1
	fi
}

entry=$("$CROSS"readelf -h "$OUT/vmlinux.elf" | awk '/Entry point/{print $4}')
expect 0x80500000 "$entry" 'entry en 0x80500000 (load-$(CONFIG_INTEL_MIPS))'

endian=$("$CROSS"readelf -h "$OUT/vmlinux.elf" | grep -o 'big endian' | head -1)
expect 'big endian' "$endian" 'big-endian (como el userland de RouterOS)'

dtbs=$("$CROSS"nm "$OUT/vmlinux.elf" | awk '/__dtb_start/{s=$1} /__dtb_end/{e=$1} END{print (s&&e)?"si":"no"}')
expect si "$dtbs" "DTB norrland enlazado en el kernel"

inird=$("$CROSS"nm "$OUT/vmlinux.elf" | grep -c __initramfs_start)
expect 1 "$inird" "initramfs enlazada en el kernel"

[ "$fail" = 0 ] && echo "  imagen OK" || { echo "  imagen NO valida"; exit 1; }
