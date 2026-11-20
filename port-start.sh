#!/bin/bash
# Primer paso del port nativo: llevar el driver GSWIP XRX500 de 6.18 a 5.6.3
# y sacar la lista de errores de compilacion (mapa del trabajo).
set -u
T=/opt/ros-port/linux-5.6.3
S=/opt/ros-port/linux-6.18
D=$T/drivers/net/dsa/xr

mkdir -p "$D"
cp -v $S/drivers/net/dsa/lantiq/lantiq_gswip_common.c "$D"/ 2>/dev/null
cp -v $S/drivers/net/dsa/lantiq/lantiq_gswip_xrx500.c "$D"/ 2>/dev/null
cp -v $S/drivers/net/dsa/lantiq/lantiq_gswip.h "$D"/ 2>/dev/null
cp -v $S/net/dsa/tag_gswip3.c "$D"/ 2>/dev/null

cat > "$D/Makefile" <<'EOF'
obj-$(CONFIG_NET_DSA_XR_GSWIP) += lantiq_gswip_common.o lantiq_gswip_xrx500.o tag_gswip3.o
EOF

# enganchar en drivers/net/dsa/Makefile (idempotente)
if ! grep -q "dsa/xr/" "$T/drivers/net/dsa/Makefile"; then
  echo 'obj-$(CONFIG_NET_DSA_XR_GSWIP) += xr/' >> "$T/drivers/net/dsa/Makefile"
fi

# Kconfig (idempotente)
if ! grep -q "NET_DSA_XR_GSWIP" "$T/drivers/net/dsa/Kconfig"; then
  cat >> "$T/drivers/net/dsa/Kconfig" <<'EOF'

config NET_DSA_XR_GSWIP
	tristate "Lantiq/Intel XRX500 GSWIP switch"
	depends on NET_DSA
	help
	  Port en curso del driver GSWIP del XRX500 desde el arbol 6.18.
EOF
fi

cd "$T" || exit 1
if [ ! -f .config ]; then
  echo "== sin .config: generando defconfig =="
  make ARCH=mips CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- defconfig >/dev/null 2>&1
fi
scripts/config --enable NET_DSA --enable NET_DSA_XR_GSWIP 2>/dev/null
make ARCH=mips CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- olddefconfig >/dev/null 2>&1

echo "== compilando el modulo =="
make ARCH=mips CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- -j4 drivers/net/dsa/xr/ > /tmp/xr-build.log 2>&1
echo "exit=$?"
echo "== errores =="
grep -E "error:|fatal error:" /tmp/xr-build.log | sed 's/.*\(error:.*\)/\1/' | sort | uniq -c | sort -rn | head -25
echo "== total errores: $(grep -cE "error:" /tmp/xr-build.log) =="
