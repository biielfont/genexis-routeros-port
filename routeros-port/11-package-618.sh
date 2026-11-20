#!/bin/bash
#
# 11-package-618.sh - empaqueta el kernel 6.18 con DTB de placa y entry correcta
#
# El punto de entrada cambia cada vez que el kernel crece: se lee del ELF y se
# mete en el uImage. Con la entry vieja, U-Boot salta a basura y la placa se
# resetea sin decir nada (sintoma que nos costo un rato).
#
set -e

K=/opt/ros-port/linux-6.18
OUT=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/out
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu

cd "$K"

${CROSS}-gcc -E -undef -D__DTS__ -x assembler-with-cpp -I include \
	-I arch/mips/boot/dts/intel-mips -o /tmp/n.dts \
	arch/mips/boot/dts/intel-mips/norrland.dts
./scripts/dtc/dtc -I dts -O dtb -o arch/mips/intel-mips/norrland.dtb /tmp/n.dts 2>/dev/null
echo "dtb: $(wc -c < arch/mips/intel-mips/norrland.dtb) bytes"

touch arch/mips/intel-mips/norrland_dtb.S
make ARCH=mips CROSS_COMPILE=${CROSS}- -j4 vmlinux >/tmp/vm.log 2>&1 || { grep -E "error:" /tmp/vm.log | head; exit 1; }

${CROSS}-objcopy -O binary vmlinux /tmp/vmlinux.bin
ENTRY=$(${CROSS}-readelf -h vmlinux | awk '/Entry point/ {print $4}')
echo "entry: $ENTRY"

mkimage -A mips -O linux -T kernel -C none -a 0x80500000 -e "$ENTRY" \
	-n "ED500 6.18 gswip" -d /tmp/vmlinux.bin "$OUT/uImage-618" >/dev/null

ls -l "$OUT/uImage-618"
echo "listo: $OUT/uImage-618 (entry $ENTRY)"
