#!/bin/bash
#
# verify-offline.sh - verificaciones del .y3 y del arranque NAND que NO
# escriben NAND. No abre /dev/mtd ni /dev/ubi: todo se hace sobre ficheros
# en /tmp y sobre los artefactos de out/.
#
# Uso:
#   bash tools/verify-offline.sh
#
# Requiere el arbol de build (/opt/ros-port/linux-5.6.3), las fuentes de
# U-Boot (/opt/qemu-9.2.0/roms/u-boot), gcc, mkenvimage, cpio,
# ubireader_extract_files y python3. El .y3 stock es opcional; si esta, se
# comprueba como imagen de recuperacion y el update_image de U-Boot.
#
set -eu

AQUI=$(cd "$(dirname "$0")/.." && pwd)
cd "$AQUI"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

Y3=out/ED500-routeros-7.17-nand.y3
UIMAGE=out/uImage-563
CPIO=/opt/ros-port/linux-5.6.3/usr/initramfs_data.cpio
DTB=/opt/ros-port/linux-5.6.3/arch/mips/boot/dts/intel-mips/norrland.dtb
UBOOT=${UBOOT_SRC:-/opt/qemu-9.2.0/roms/u-boot}
STOCK=out/ED500-stock-original.y3

fallo() {
	echo "FALLO: $*" >&2
	exit 1
}

ok() {
	echo "  OK   $*"
}

necesita() {
	command -v "$1" >/dev/null 2>&1 || fallo "falta '$1'"
}

[ -f "$Y3" ] || fallo "falta $Y3; ejecuta build-563.sh y tools/make-y3.sh"
[ -f "$UIMAGE" ] || fallo "falta $UIMAGE; ejecuta build-563.sh"
necesita python3
necesita md5sum
necesita cmp
necesita cpio
necesita gcc
necesita mkenvimage
necesita ubireader_extract_files
necesita ubireader_display_info
[ -d "$UBOOT/tools/env" ] || fallo "falta $UBOOT/tools/env (define UBOOT_SRC)"
[ -f "$CPIO" ] || fallo "falta $CPIO; ejecuta build-563.sh"
[ -f "$DTB" ] || fallo "falta $DTB"

echo "== Artefactos =="
ls -l "$Y3" "$UIMAGE"
md5sum "$Y3" "$UIMAGE"

echo "== Contenedor .y3 =="
python3 08-y3tool.py info "$Y3" | tee "$TMP/y3.info"
grep -q 'size declarado.*OK' "$TMP/y3.info" || fallo "tamano del .y3 incoherente"
grep -q '<-- COINCIDE' "$TMP/y3.info" || fallo "MD5 del .y3 incoherente"
grep -q 'firma *0 bytes' "$TMP/y3.info" || fallo "el .y3 lleva firma inesperada"
ok "tamano, MD5 y firma"

echo "== Contenido de la UBIFS =="
rm -rf "$TMP/y3" "$TMP/tree"
python3 08-y3tool.py unpack "$Y3" "$TMP/y3" >/dev/null
ubireader_display_info "$TMP/y3/rootfs.ubifs" > "$TMP/ubifs.info" 2>&1
grep -q 'leb_cnt: 422' "$TMP/ubifs.info" || fallo "LEB count inesperado"
grep -q 'max_leb_cnt: 480' "$TMP/ubifs.info" || fallo "max_leb_cnt inesperado"
ubireader_extract_files -o "$TMP/tree" "$TMP/y3/rootfs.ubifs" >/dev/null 2>&1
[ -f "$TMP/tree/boot/uImage" ] || fallo "falta /boot/uImage"
[ -f "$TMP/tree/boot/norrland.dtb" ] || fallo "falta /boot/norrland.dtb"
[ -d "$TMP/tree/rw" ] || fallo "falta /rw"
[ -f "$TMP/tree/pad" ] || fallo "falta /pad"
cmp -s "$TMP/tree/boot/uImage" "$UIMAGE" || fallo "/boot/uImage no coincide"
cmp -s "$TMP/tree/boot/norrland.dtb" "$DTB" || fallo "/boot/norrland.dtb no coincide"
[ "$(stat -c%s "$TMP/tree/pad")" = 31457280 ] || fallo "/pad no mide 30 MiB"
ok "/boot/uImage y DTB byte a byte; /rw y /pad presentes"

echo "== Nombres RouterOS (ros-name) =="
DTC=${DTC:-/opt/ros-port/linux-5.6.3/scripts/dtc/dtc}
for n in ether1 ether2 ether3 ether4; do
	"$DTC" -I dtb -O dts "$DTB" 2>/dev/null | grep -q "ros-name = \"$n\"" || fallo "falta ros-name $n en el DTB"
done
ok "DTB con ros-name ether1..4"

echo "== Initramfs =="
cpio -itv < "$CPIO" 2>/dev/null | grep -q 'bin/busybox$' || fallo "falta /bin/busybox"
cpio -itv < "$CPIO" 2>/dev/null | grep -q 'bin/devlog$' || fallo "falta /bin/devlog"
cpio -itv < "$CPIO" 2>/dev/null | grep -q 'usr/sbin/fw_printenv$' || fallo "falta fw_printenv"
cpio -itv < "$CPIO" 2>/dev/null | grep -q 'usr/sbin/fw_setenv$' || fallo "falta fw_setenv"
cpio -i --to-stdout init < "$CPIO" 2>/dev/null > "$TMP/init"
grep -q 'cp /bin/busybox \$R/bin/busybox' "$TMP/init" || fallo "init no copia busybox"
grep -q 'cp /bin/devlog \$R/bin/devlog' "$TMP/init" || fallo "init no copia devlog"
grep -q 'ROOTVOL=rootfs_0' "$TMP/init" || fallo "init no fija rootfs_0"
grep -q 'for vol in rootfs_0 rootfs_1' "$TMP/init" && fallo "init sigue montando rootfs_1"
grep -q 'boot_cnt_alt' "$TMP/init" && fallo "init sigue con el contador alt"
grep -q 'chroot \$R /bin/busybox sh /bin/netup' "$TMP/init" || fallo "falta chroot netup"
grep -q 'chroot \$R /bin/busybox sh /bin/bootok' "$TMP/init" || fallo "falta chroot bootok"
grep -q '/proc/net/tcp6' "$TMP/init" || fallo "bootok no comprueba tcp6"
ok "rootfs_0 unico, flag primary y tcp6"

if [ -f ros/rootfs/sbin/sysinit ]; then
	echo "== Rutas de autorun de sysinit =="
	for ruta in /flash/autorun.scr /rw/autorun.scr /rw/store/autorun.scr /pckg/branding/rw/autorun.scr; do
		strings ros/rootfs/sbin/sysinit | grep -qF "$ruta" || fallo "sysinit no busca $ruta"
	done
	ok "sysinit busca las cuatro rutas que escribe el init"
fi

echo "== Entorno U-Boot (host, ficheros; sin UBI real) =="
mkdir -p "$TMP/fw/generated"
: > "$TMP/fw/generated/autoconf.h"
: > "$TMP/fw/config.h"
printf '#define PLAIN_VERSION "verify"\n#define U_BOOT_VERSION "verify"\n' > "$TMP/fw/version.h"
printf 'root_vol=rootfs_0\nboot_cnt_primary=3\nboot_cnt_alt=7\n' > "$TMP/fw/env.txt"
mkenvimage -r -s 0x1f000 -o "$TMP/fw/env1.bin" "$TMP/fw/env.txt"
cp "$TMP/fw/env1.bin" "$TMP/fw/env2.bin"
printf '%s\n%s\n' "$TMP/fw/env1.bin 0x0 0x1f000" "$TMP/fw/env2.bin 0x0 0x1f000" > "$TMP/fw/fw_env.config"
gcc -O2 -DUSE_HOSTCC -DTEXT_BASE=0 -DCONFIG_FILE='"/etc/fw_env.config"' \
	-I"$TMP/fw" -I"$UBOOT/tools" -I"$UBOOT/tools/env" \
	-idirafter "$UBOOT/include" -idirafter "$UBOOT/arch/mips/include" \
	-o "$TMP/fw/fw_printenv" \
	"$UBOOT/tools/env/fw_env_main.c" "$UBOOT/tools/env/fw_env.c" \
	"$UBOOT/tools/env/crc32.c" "$UBOOT/tools/env/ctype.c" \
	"$UBOOT/tools/env/linux_string.c" "$UBOOT/tools/env/env_attr.c" \
	"$UBOOT/tools/env/env_flags.c" 2>"$TMP/fw/gcc.log" || {
		cat "$TMP/fw/gcc.log" >&2
		fallo "no se pudo compilar fw_printenv host"
	}
cp "$TMP/fw/fw_printenv" "$TMP/fw/fw_setenv"
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw/fw_env.config" -n root_vol)" = rootfs_0 ] || fallo "lectura root_vol"
"$TMP/fw/fw_setenv" -c "$TMP/fw/fw_env.config" boot_cnt_primary 0
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw/fw_env.config" -n boot_cnt_primary)" = 0 ] || fallo "escritura boot_cnt_primary"
# Guarda una copia valida para el test de bootok antes de corromper las copias.
cp "$TMP/fw/env1.bin" "$TMP/env.bin"
printf X | dd of="$TMP/fw/env1.bin" bs=1 seek=100 conv=notrunc status=none
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw/fw_env.config" -n root_vol 2>/dev/null)" = rootfs_0 ] || fallo "fallback env2"
printf X | dd of="$TMP/fw/env2.bin" bs=1 seek=100 conv=notrunc status=none
if "$TMP/fw/fw_printenv" -c "$TMP/fw/fw_env.config" -n root_vol >/dev/null 2>"$TMP/corrupt.err"; then
	fallo "el entorno corrupto deberia fallar"
fi
ok "lectura, escritura, copia redundante y CRC"

echo "== Logica de bootok (host, ficheros) =="
awk 'index($0,"bin/bootok <<"){f=1;next} f && $0=="BOOTOK"{exit} f' init-initramfs.sh > "$TMP/bootok.orig"
[ -s "$TMP/bootok.orig" ] || fallo "no se pudo extraer bootok"
cat > "$TMP/b" <<'EOF'
#!/bin/sh
exec "$@"
EOF
chmod +x "$TMP/b"
printf '%s\n' "$TMP/env.bin 0x0 0x1f000" > "$TMP/fw_env.config"
cp "$TMP/bootok.orig" "$TMP/bootok.test"
sed -i \
	-e "s#B=/bin/busybox#B=$TMP/b#" \
	-e "s#/proc/cmdline#$TMP/cmdline#g" \
	-e "s#LOG=/flash/rw/bootok.log#LOG=$TMP/bootok.log#" \
	-e "s#/bin/fw_printenv#$TMP/fw/fw_printenv#g" \
	-e "s#/bin/fw_setenv#$TMP/fw/fw_setenv#g" \
	-e "s#/flash/rw/fw_env.config#$TMP/fw_env.config#g" \
	-e "s#/flash/rw/autorun.scr#$TMP/autorun.scr#g" \
	-e "s#/flash/rw/store/autorun.scr#$TMP/store-autorun.scr#g" \
	-e "s#\$B sleep 10#:#g" \
	-e 's#svc_up() {#svc_up() { return ${SVC:-0};#' \
	"$TMP/bootok.test"
grep -q "B=$TMP/b" "$TMP/bootok.test" || fallo "reemplazo B en bootok"
grep -q "LOG=$TMP/bootok.log" "$TMP/bootok.test" || fallo "reemplazo LOG en bootok"

printf 'root=ubi0:rootfs_0 ubi.mtd=ubi,0,30\n' > "$TMP/cmdline"
cat > "$TMP/autorun.scr" <<'EOF'
/delay 5
/user set admin password="ed500"
/interface bridge add name=bridge
EOF
cp "$TMP/autorun.scr" "$TMP/store-autorun.scr"
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" root_vol rootfs_0
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" boot_cnt_primary 5
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" boot_cnt_alt 6
rm -f "$TMP/bootok.log"
SVC=0 sh "$TMP/bootok.test"
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw_env.config" -n boot_cnt_primary)" = 0 ] || fallo "rootfs_0 no baja primary"
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw_env.config" -n boot_cnt_alt)" = 6 ] || fallo "rootfs_0 toca alt"
grep -q 'boot_cnt_primary=0 (rootfs_0)' "$TMP/bootok.log" || fallo "log rootfs_0"
! grep -q 'user set admin password' "$TMP/autorun.scr" || fallo "autorun no limpio"
! grep -q 'user set admin password' "$TMP/store-autorun.scr" || fallo "store/autorun no limpio"
ok "rootfs_0: primary=0, autorun limpio"

printf 'root=ubi0:rootfs_1 ubi.mtd=ubi,0,30\n' > "$TMP/cmdline"
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" root_vol rootfs_1
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" boot_cnt_primary 5
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" boot_cnt_alt 6
rm -f "$TMP/bootok.log"
SVC=0 sh "$TMP/bootok.test"
# rootfs_1 no es un banco activo: el ayudante no debe tocar el flag.
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw_env.config" -n boot_cnt_primary)" = 5 ] || fallo "rootfs_1 toca primary"
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw_env.config" -n boot_cnt_alt)" = 6 ] || fallo "rootfs_1 toca alt"
grep -q 'actual=rootfs_1 no es rootfs_0' "$TMP/bootok.log" || fallo "log rootfs_1"
ok "rootfs_1 se ignora: no toca el flag"

printf 'root=ubi0:rootfs_0 ubi.mtd=ubi,0,30\n' > "$TMP/cmdline"
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" root_vol rootfs_0
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" boot_cnt_primary 5
"$TMP/fw/fw_setenv" -c "$TMP/fw_env.config" boot_cnt_alt 6
rm -f "$TMP/bootok.log"
SVC=1 sh "$TMP/bootok.test"
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw_env.config" -n boot_cnt_primary)" = 5 ] || fallo "servicio caido toca primary"
[ "$("$TMP/fw/fw_printenv" -c "$TMP/fw_env.config" -n boot_cnt_alt)" = 6 ] || fallo "servicio caido toca alt"
grep -q 'sysinit no responde' "$TMP/bootok.log" || fallo "log servicio caido"
ok "servicio caido: contadores intactos"

printf 'root=ubi0:rootfs_0 ubi.mtd=ubi,0,30\n' > "$TMP/cmdline"
printf '%s\n' "$TMP/no-existe 0x0 0x1f000" > "$TMP/fw_env.config"
rm -f "$TMP/bootok.log"
SVC=0 sh "$TMP/bootok.test"
grep -q 'fw_printenv no lee root_vol' "$TMP/bootok.log" || fallo "log entorno ilegible"
ok "entorno ilegible: no escribe contadores"

if [ -f "$STOCK" ]; then
	echo "== Recuperacion stock =="
	grep -q 'update_image=.*yimage burn rootfs_0' logs/serial-cmd.log || fallo "U-Boot update_image no escribe rootfs_0"
	grep -q 'update_image=.*setenv root_vol rootfs_0' logs/serial-cmd.log || fallo "U-Boot update_image no fija root_vol"
	python3 08-y3tool.py info "$STOCK" > "$TMP/stock.info"
	grep -q '<-- COINCIDE' "$TMP/stock.info" || fallo "MD5 del stock no coincide"
	grep -q 'firma *0 bytes' "$TMP/stock.info" || fallo "el stock lleva firma inesperada"
	rm -rf "$TMP/stock" "$TMP/stockroot"
	python3 08-y3tool.py unpack "$STOCK" "$TMP/stock" >/dev/null
	ubireader_extract_files -o "$TMP/stockroot" "$TMP/stock/rootfs.ubifs" >/dev/null 2>&1
	[ -f "$TMP/stockroot/boot/uImage" ] || fallo "stock sin /boot/uImage"
	[ -f "$TMP/stockroot/boot/norrland.dtb" ] || fallo "stock sin /boot/norrland.dtb"
	ok "stock intacto; run update_image lo devuelve a rootfs_0"
else
	echo "  SKIP recuperacion stock: no esta $STOCK"
fi

echo
echo "Verificacion offline completa."
echo "NAND intacta: no se ha abierto /dev/mtd ni /dev/ubi."
echo "El arranque real, la persistencia, el reset/LEDs y el primer login siguen pendientes de placa."
