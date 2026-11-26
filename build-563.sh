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

# drivers y nodos propios del ED500 (LEDs SSO, RGB SK9822 y boton reset).
# Es idempotente: se puede ejecutar en cada build sin duplicar nada.
python3 "$AQUI/tools/ed500-hardware.py" "$T" || {
  echo "hardware FALLO: no se pudieron aplicar los drivers/nodos del ED500"
  exit 1
}

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
# Identidad RouterBoot sintetica para el MTD de RAM: flash.ko lee de ahi
# product ID, MAC y serial. Sin ella el MTD en 0xFF da hard_size=0xFFFFFFFF
# y vmalloc falla antes de crear /dev/flash. No toca la NAND ni la licencia.
python3 "$AQUI/rb_hardconfig.py" "$AQUI/ros/rb_hardconfig.bin" || {
  echo "hardconfig FALLO: no se pudo generar"
  exit 1
}
cp "$AQUI/ros/rb_hardconfig.bin" /opt/ros-port/initramfs/rb_hardconfig.bin || {
  echo "hardconfig FALLO: no se pudo copiar al initramfs"
  exit 1
}
echo "initramfs: hard config RouterBoot sintetico incluido"
if [ -s "$AQUI/license.key" ]; then
  cp "$AQUI/license.key" /opt/ros-port/initramfs/license.key || {
    echo "license FALLO: no se pudo copiar al initramfs"
    exit 1
  }
  echo "initramfs: license.key incluida"
fi

# herramienta de diagnostico del PHY (lee BMCR/BMSR por MDIO)
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/phyreg "$AQUI/phyreg.c" \
  || echo "phyreg FALLO"
# contadores RMON del switch (ETHTOOL_GSTATS)
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/swstats "$AQUI/swstats.c" \
  || echo "swstats FALLO"
# reloj de jiffies en userspace (sustituye al jiffies.ko roto del rootfs)
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/tickfile "$AQUI/tools/tickfile.c" \
  || { echo "tickfile FALLO"; exit 1; }
# mide si el kernel duerme de verdad (sleep/usleep/nanosleep vs uptime)
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/timediag "$AQUI/tools/timediag.c" \
  || { echo "timediag FALLO"; exit 1; }
# libumsg::getJiffies() suma 30000 = 300*100: RouterOS espera 100 Hz
# aunque el kernel vaya a 250. Si tickfile vuelve a 250, el login caduca
# antes de autenticar y el proceso muere con SIGSEGV.
if ! grep -q '^#define ROS_HZ 100$' "$AQUI/tools/tickfile.c"; then
  echo "TICKFILE FALLO: ROS_HZ debe ser 100 (libumsg espera 100 Hz)"
  exit 1
fi
echo "tickfile: ROS_HZ=100 (getJiffies 0-based a 100 Hz)"
# mini-strace ptrace para localizar el broken path de sysinit
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/sysopen "$AQUI/sysopen.c" \
  || echo "sysopen FALLO"
# logger minimo que crea /dev/log y lo mantiene enlazado
${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/devlog "$AQUI/devlog.c" \
  || echo "devlog FALLO"
# fw_printenv/fw_setenv para resetear el flag de arranque de U-Boot desde
# el init; sin esto iboot vuelve al banco stock tras varios reinicios.
bash "$AQUI/tools/build-fwenv.sh" /opt/ros-port/initramfs || {
  echo "fwenv FALLO: no se pudieron construir fw_printenv/fw_setenv"
  exit 1
}
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
  --enable COMPAT_32BIT_TIME \
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
  --enable MTD_MTDRAM \
  --set-val MTDRAM_TOTAL_SIZE 16384 \
  --set-val MTDRAM_ERASE_SIZE 128 \
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
  --enable NET_SWITCHDEV \
  --enable NET_DSA_TAG_GSWIP3 \
  --enable NET_DSA_XR_GSWIP \
  --enable NET_DSA_TAG_GSWIP \
  --enable PHYLINK \
  --enable INTEL_XRX500_NET \
  --enable INTEL_XRX500_BM \
  --enable INTEL_XRX500_CBM_CONDUIT \
  --enable INTEL_XWAY_PHY \
  --enable DEVMEM \
  --enable VLAN_8021Q \
  --enable BRIDGE_VLAN_FILTERING \
  --enable JUMP_LABEL \
  --enable NAMESPACES \
  --enable USER_NS \
  --enable XFRM \
  --enable XFRM_USER \
  --enable INET_XFRM_MODE_TRANSPORT \
  --enable INET_XFRM_MODE_TUNNEL \
  --enable INET_XFRM_MODE_BEET \
  --enable INET6_XFRM_MODE_TRANSPORT \
  --enable INET6_XFRM_MODE_TUNNEL \
  --enable INET6_XFRM_MODE_ROUTEOPTIMIZATION \
  --enable INET6_XFRM_MODE_BEET \
  --enable INET_IPCOMP \
  --enable INET6_IPCOMP \
  --enable NET_SCHED \
  --enable NET_CLS \
  --disable NET_CLS_ACT \
  --enable MPLS \
  --enable MPLS_ROUTING \
  --disable NETFILTER_INGRESS \
  --enable NET_SCH_HTB \
  --enable NET_SCH_SFQ \
  --enable NET_SCH_PRIO \
  --disable NET_SCH_INGRESS \
  --disable NET_CLS_FW \
  --disable NET_CLS_U32 \
  --disable NET_ACT_GACT \
  --disable NET_ACT_MIRRED \
  --disable NET_ACT_POLICE \
  --enable NETFILTER_XTABLES \
  --enable NF_NAT \
  --enable IP_NF_IPTABLES \
  --enable IP_NF_FILTER \
  --enable IP_NF_MANGLE \
  --enable IP_NF_NAT \
  --enable IP_NF_TARGET_MASQUERADE \
  --enable IP6_NF_IPTABLES \
  --enable IP6_NF_FILTER \
  --enable IP6_NF_MANGLE \
  --enable IP6_NF_NAT \
  --enable NETFILTER_XT_MATCH_CONNTRACK \
  --enable NETFILTER_XT_TARGET_MASQUERADE \
  --enable BRIDGE_NETFILTER \
  --enable BRIDGE_EBTABLES \
  --enable MII \
  --enable I2C \
  --enable GPIOLIB \
  --enable PINCTRL \
  --enable PINCTRL_EQUILIBRIUM \
  --enable GPIO_ED500_BUTTONS \
  --enable HWMON \
  --enable NEW_LEDS \
  --enable LEDS_CLASS \
  --enable LEDS_INTEL_SSO \
  --enable LEDS_SK9822 \
  --enable KEYS \
  --enable FILE_LOCKING \
  --enable FS_POSIX_ACL \
  --enable LWTUNNEL \
  --enable NET_FOU \
  --enable NET_UDP_TUNNEL \
  --enable IPV6_MULTIPLE_TABLES \
  --enable IPV6_SUBTREES

if ! make ARCH=mips CROSS_COMPILE=$CROSS olddefconfig > /opt/olddef.log 2>&1; then
  echo "olddefconfig FALLO"
  tail -20 /opt/olddef.log
  exit 1
fi
echo "olddefconfig=0"

# NET_CLS_ACT mete miniq_ingress/miniq_egress en struct net_device y desplaza
# pcpu_refcnt de 672 a 680. Los modulos de RouterOS se compilaron con el
# layout de 672; packet_hook hace dev_put() sobre un campo equivocado y el
# kernel revienta al cargarlo (reproducido en QEMU). Debe quedar apagado.
if grep -q '^CONFIG_NET_CLS_ACT=' .config; then
  echo "CONFIG FALLO: NET_CLS_ACT debe estar apagado (ABI de struct net_device)"
  exit 1
fi
if grep -q '^CONFIG_NETFILTER_INGRESS=' .config; then
  echo "CONFIG FALLO: NETFILTER_INGRESS debe estar apagado (ABI de struct net_device)"
  exit 1
fi
if ! grep -q '^CONFIG_MPLS=' .config || ! grep -q '^CONFIG_MPLS_ROUTING=' .config; then
  echo "CONFIG FALLO: MPLS/MPLS_ROUTING deben estar activos (ABI de struct net_device)"
  exit 1
fi

if ! grep -q 'bridge2.ko sustituye al bridge del kernel' net/bridge/br.c; then
  echo "CONFIG FALLO: falta el stub de br_init para bridge2.ko"
  exit 1
fi

for s in CONFIG_BINFMT_SCRIPT CONFIG_RESET_CONTROLLER CONFIG_RESET_LANTIQ CONFIG_POWER_RESET CONFIG_POWER_RESET_SYSCON CONFIG_NET_DSA_TAG_GSWIP3 CONFIG_NET_DSA_TAG_GSWIP CONFIG_FUTEX CONFIG_EPOLL CONFIG_EVENTFD CONFIG_TIMERFD CONFIG_POSIX_TIMERS CONFIG_NETFILTER CONFIG_NF_CONNTRACK CONFIG_MULTIUSER CONFIG_BRIDGE CONFIG_SHMEM CONFIG_BLOCK CONFIG_IP_ADVANCED_ROUTER CONFIG_TMPFS CONFIG_SQUASHFS CONFIG_SQUASHFS_XZ CONFIG_BLK_DEV_LOOP CONFIG_INOTIFY_USER CONFIG_SYSVIPC CONFIG_FHANDLE CONFIG_IP_MULTIPLE_TABLES CONFIG_MIPS_FP_SUPPORT CONFIG_FW_LOADER CONFIG_EXTRA_FIRMWARE CONFIG_INTEL_GRX500_CGU_CLK CONFIG_SERIAL_LANTIQ CONFIG_NET_DSA CONFIG_NET_SWITCHDEV CONFIG_NET_DSA_XR_GSWIP CONFIG_INTEL_XRX500_NET CONFIG_INTEL_XRX500_BM CONFIG_INTEL_XRX500_CBM_CONDUIT CONFIG_INTEL_XWAY_PHY CONFIG_MTD CONFIG_MTD_BLOCK CONFIG_MTD_RAW_NAND CONFIG_MTD_NAND_CORE CONFIG_MTD_NAND_ECC_SW_HAMMING CONFIG_MTD_NAND_ECC_SW_BCH CONFIG_MTD_NAND_LANTIQ_XRX500 CONFIG_MTD_OF_PARTS CONFIG_MTD_UBI CONFIG_MTD_UBI_BLOCK CONFIG_MTD_MTDRAM CONFIG_MTDRAM_TOTAL_SIZE CONFIG_MTDRAM_ERASE_SIZE CONFIG_UBIFS_FS CONFIG_UBIFS_FS_ADVANCED_COMPR CONFIG_UBIFS_FS_LZO CONFIG_UBIFS_FS_ZLIB CONFIG_UBIFS_FS_ZSTD CONFIG_BCH CONFIG_LZO_DECOMPRESS CONFIG_DEVTMPFS CONFIG_VLAN_8021Q CONFIG_BRIDGE_VLAN_FILTERING CONFIG_JUMP_LABEL CONFIG_NAMESPACES CONFIG_USER_NS CONFIG_XFRM CONFIG_INET_XFRM_TUNNEL CONFIG_INET6_XFRM_TUNNEL CONFIG_INET_IPCOMP CONFIG_INET6_IPCOMP CONFIG_NET_SCHED CONFIG_MPLS CONFIG_MPLS_ROUTING CONFIG_NETFILTER_XTABLES CONFIG_NF_NAT CONFIG_IP_NF_IPTABLES CONFIG_IP_NF_NAT CONFIG_MII CONFIG_I2C CONFIG_GPIOLIB CONFIG_PINCTRL CONFIG_PINCTRL_EQUILIBRIUM CONFIG_GPIO_ED500_BUTTONS CONFIG_HWMON CONFIG_NEW_LEDS CONFIG_LEDS_CLASS CONFIG_LEDS_INTEL_SSO CONFIG_LEDS_SK9822 CONFIG_KEYS CONFIG_LWTUNNEL CONFIG_NET_FOU CONFIG_NET_UDP_TUNNEL CONFIG_SKB_EXTENSIONS; do
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
# El initramfs va comprimido dentro del kernel. Si no se borran estos
# objetos, make puede reutilizar el cpio de un build anterior y el init
# que arranca no es el del proyecto (ya paso con NAND_PERSIST).
rm -f usr/initramfs_data.cpio usr/initramfs_data.cpio.gz usr/initramfs_data.o
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

# El layout que usan los modulos de RouterOS: dev_addr en 476 y pcpu_refcnt
# en 672. NET_CLS_ACT y NETFILTER_INGRESS mueven esos campos; MPLS_ROUTING
# aporta mpls_ptr antes de dev_addr. Comprobar el vmlinux real, no solo .config.
if command -v pahole >/dev/null 2>&1; then
  pahole -C net_device vmlinux > /tmp/nd-abi.txt 2>/dev/null || true
  if ! grep -q 'dev_addr.*476' /tmp/nd-abi.txt || ! grep -q 'pcpu_refcnt.*672' /tmp/nd-abi.txt; then
    echo "ABI FALLO: net_device no coincide (dev_addr=476, pcpu_refcnt=672)"
    grep -E 'dev_addr|pcpu_refcnt|name\[' /tmp/nd-abi.txt | head -8
    exit 1
  fi
  echo "abi: dev_addr=476 pcpu_refcnt=672"
else
  echo "ABI AVISO: pahole no disponible; no se comprueba el layout"
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
for n in ether1 ether2 ether3 ether4; do
  if ! "$T/scripts/dtc/dtc" -I dtb -O dts "$DTB" 2>/dev/null | grep -q "ros-name = \"$n\""; then
    echo "DTB FALLO: falta ros-name $n (net no creara la interfaz)"
    exit 1
  fi
done
echo "dtb: BCH-4 + BBT + ubi.mtd=ubi + ros-name ether1..4"

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
# Se escribe a un temporal y se renombra al final: si el build se corta, el
# cazador TFTP sigue teniendo una imagen completa y arrancable en su sitio.
NUEVA="$OUT/uImage-563.new"
rm -f "$NUEVA"
if ! mkimage -A mips -O linux -T kernel -C none -a 0x80500000 -e "$ENTRY" \
        -n "Linux 5.6.3 ED500 (RouterOS base)" \
        -d /tmp/vmlinux.bin "$NUEVA" > /dev/null 2>&1; then
  echo "mkimage FALLO"
  exit 1
fi
mv -f "$NUEVA" "$OUT/uImage-563" || {
  echo "mv FALLO: no se pudo publicar uImage-563"
  exit 1
}
if [ ! -s "$OUT/uImage-563" ]; then
  echo "uImage FALLO: no se creo"
  exit 1
fi
ls -l "$OUT/uImage-563" | awk '{print "uImage:", $5, "bytes"}'
