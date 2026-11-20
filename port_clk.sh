#!/bin/bash
# Porta el driver de relojes del GRX500 (clk-grx500 + CGU) del arbol 6.18 al 5.6.3.
# Sin el, el ASC se queda en -EPROBE_DEFER y la consola no aparece.
set -e

SRC=/opt/ros-port/linux-6.18
DST=/opt/ros-port/linux-5.6.3

mkdir -p "$DST/drivers/clk/intel"
cp "$SRC/drivers/clk/intel/clk-grx500.c"   "$DST/drivers/clk/intel/"
cp "$SRC/drivers/clk/intel/clk-cgu.c"      "$DST/drivers/clk/intel/"
cp "$SRC/drivers/clk/intel/clk-cgu.h"      "$DST/drivers/clk/intel/"
cp "$SRC/drivers/clk/intel/clk-cgu-pll.c"  "$DST/drivers/clk/intel/"
cp "$SRC/drivers/clk/intel/clk-cgu-pll.h"  "$DST/drivers/clk/intel/"

mkdir -p "$DST/include/dt-bindings/clock"
cp "$SRC/include/dt-bindings/clock/intel,grx500-clk.h" "$DST/include/dt-bindings/clock/"

# Kconfig del directorio
cat > "$DST/drivers/clk/intel/Kconfig" <<'EOF'
# SPDX-License-Identifier: GPL-2.0-only
config INTEL_CGU_CLK
	bool "Intel CGU clock support"
	depends on COMMON_CLK
	help
	  Support for the Intel CGU clock controller found on LGM/GRX500.

choice
	prompt "SoC platform selection"
	depends on INTEL_CGU_CLK
	default INTEL_GRX500_CGU_CLK

config INTEL_GRX500_CGU_CLK
	bool "GRX500 CLK"
	help
	  Clock driver of GRX500 platform.

endchoice
EOF

cat > "$DST/drivers/clk/intel/Makefile" <<'EOF'
# SPDX-License-Identifier: GPL-2.0-only
obj-$(CONFIG_INTEL_GRX500_CGU_CLK)	+= clk-grx500.o clk-cgu.o clk-cgu-pll.o
EOF

# Enganchar el subdirectorio en el Kconfig/Makefile de drivers/clk
grep -q 'source "drivers/clk/intel/Kconfig"' "$DST/drivers/clk/Kconfig" || \
	sed -i '1i source "drivers/clk/intel/Kconfig"' "$DST/drivers/clk/Kconfig"
grep -q 'obj-y += intel/' "$DST/drivers/clk/Makefile" || \
	echo 'obj-y += intel/' >> "$DST/drivers/clk/Makefile"

echo "== ficheros colocados =="
ls -l "$DST/drivers/clk/intel/"
echo "== enganchado =="
head -3 "$DST/drivers/clk/Kconfig"
tail -2 "$DST/drivers/clk/Makefile"
