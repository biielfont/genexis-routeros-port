#!/bin/bash
#
# 07-port-ethernet.sh - H2c: mete el driver Ethernet xRX500 (6.18) en el arbol
# 5.6.3 y lo compila para medir cuanto hay que portar.
#
# No deja el driver activo: la opcion queda en 'n' por defecto, asi que el
# kernel del ED500 sigue compilando igual.
#
set -u

K=/opt/ros-port/linux-5.6.3
R=/opt/ros-port/refs2/lantiq
D=$K/drivers/net/ethernet/lantiq
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-

echo "== 1. copia de fuentes =="
mkdir -p "$D/cqm/grx500" "$D/dma" "$D/tmu"
cp "$R"/xrx500-cbm.c "$D"/
cp "$R"/cqm/grx500/*.c "$D/cqm/grx500/"
cp "$R"/dma/* "$D/dma/"
cp "$R"/tmu/* "$D/tmu/"
find "$D/cqm" "$D/dma" "$D/tmu" -name '*.c' | wc -l

echo "== 2. Kconfig y Makefile =="
cp "$R/Kconfig"  "$D/Kconfig"
cp "$R/Makefile" "$D/Makefile"

python3 - "$K/drivers/net/ethernet" <<'PY'
import sys, os
e = sys.argv[1]

k = os.path.join(e, "Kconfig")
s = open(k).read()
if "ethernet/lantiq/Kconfig" not in s:
    s = s.replace('source "drivers/net/ethernet/lantiq/Kconfig"', '')
    s += '\nsource "drivers/net/ethernet/lantiq/Kconfig"\n'
    open(k, "w").write(s)
    print("ethernet/Kconfig: source anadido")

m = os.path.join(e, "Makefile")
s = open(m).read()
if "+= lantiq/" not in s:
    s += "obj-$(CONFIG_INTEL_XRX500_NET) += lantiq/\n"
    open(m, "w").write(s)
    print("ethernet/Makefile: lantiq/ anadido")
PY

echo "== 3. config =="
cd "$K"
scripts/config --enable INTEL_XRX500_NET --enable INTEL_XRX500_BM
make ARCH=mips CROSS_COMPILE=$CROSS olddefconfig >/dev/null 2>&1
grep -E "CONFIG_INTEL_XRX500_(NET|BM)=" .config

echo "== 4. compilacion de prueba =="
rm -f /opt/ros-port/eth-port.log
make ARCH=mips CROSS_COMPILE=$CROSS -j4 drivers/net/ethernet/lantiq/ > /opt/ros-port/eth-port.log 2>&1
echo "rc=$?"
echo
echo "--- errores por fichero ---"
grep -oE "^\.\./[^:]*\.c:[0-9]+:[0-9]+: error:" /opt/ros-port/eth-port.log 2>/dev/null \
	| cut -d: -f1 | sort | uniq -c | sort -rn | head -12
echo
echo "--- total errores ---"
grep -c "error:" /opt/ros-port/eth-port.log 2>/dev/null
echo
echo "--- primeros 15 mensajes ---"
grep "error:" /opt/ros-port/eth-port.log 2>/dev/null | sed 's/^.*error: //' | sort | uniq -c | sort -rn | head -15
