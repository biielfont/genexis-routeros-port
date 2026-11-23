#!/bin/bash
# Compila el driver GSWIP del XRX500 en 5.6.3 y resume errores.
# Uso: xr-iter.sh [n]
set -u
T=/opt/ros-port/linux-5.6.3
SRC=/mnt/c/Users/BFR/Documents/Genexis/routeros-port
N=${1:-12}

# capa de compatibilidad
cp "$SRC/xr_compat.h" "$T/drivers/net/dsa/xr/" 2>/dev/null
python3 - "$T" <<'PY'
import sys, pathlib
t = pathlib.Path(sys.argv[1]) / "drivers/net/dsa/xr"
for f in ("lantiq_gswip_common.c", "lantiq_gswip_xrx500.c"):
    p = t / f
    if not p.exists():
        continue
    s = p.read_text(errors="replace")
    if "xr_compat.h" not in s:
        p.write_text('#include "xr_compat.h"\n' + s)
PY

cat > "$T/drivers/net/dsa/xr/Makefile" <<'EOF'
obj-$(CONFIG_NET_DSA_XR_GSWIP) += lantiq_gswip_common.o lantiq_gswip_xrx500.o
# el codigo de 6.18 usa declaraciones dentro del for (C99)
CFLAGS_lantiq_gswip_common.o := -std=gnu11
CFLAGS_lantiq_gswip_xrx500.o := -std=gnu11
EOF

cd "$T" || exit 1
make ARCH=mips CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- -j4 \
     drivers/net/dsa/xr/ > /opt/xr.log 2>&1
rc=$?
echo "exit=$rc  errores=$(grep -c 'error:' /opt/xr.log)"
echo "--- primeros $N ---"
grep -E "error:" /opt/xr.log | head -"$N"
