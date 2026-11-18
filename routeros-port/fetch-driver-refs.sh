#!/bin/bash
# Descarga las fuentes del driver Ethernet xRX500 de grische (kernel 6.18)
# para evaluar el port a 5.6.3. Solo lectura de referencia.
set -u
B="https://raw.githubusercontent.com/grische/linux/intel-mips-xrx500-v6.18/drivers/net/ethernet/lantiq"
D=/opt/ros-port/refs2/lantiq
mkdir -p "$D/cqm/grx500" "$D/dma" "$D/tmu"

get() {  # url, destino
	curl -sL "$1" -o "$2"
	printf "%8s %s\n" "$(wc -c < "$2")" "$2"
}

get "$B/Makefile"                 "$D/Makefile"
get "$B/Kconfig"                  "$D/Kconfig"
get "$B/xrx500-cbm.c"             "$D/xrx500-cbm.c"
get "$B/cqm/grx500/cbm.c"         "$D/cqm/grx500/cbm.c"
get "$B/cqm/grx500/cbm_basic.c"   "$D/cqm/grx500/cbm_basic.c"
get "$B/cqm/grx500/cbm_buf.c"     "$D/cqm/grx500/cbm_buf.c"
get "$B/cqm/grx500/cbm_intr.c"    "$D/cqm/grx500/cbm_intr.c"
get "$B/cqm/grx500/fsqm.c"        "$D/cqm/grx500/fsqm.c"
get "$B/cqm/grx500/cbm_dma.c"     "$D/cqm/grx500/cbm_dma.c"
get "$B/cqm/grx500/cbm_ports.c"   "$D/cqm/grx500/cbm_ports.c"
get "$B/dma/hdma.c"               "$D/dma/hdma.c"
get "$B/tmu/tmu_init.c"           "$D/tmu/tmu_init.c"
get "$B/tmu/drv_tmu_ll.c"         "$D/tmu/drv_tmu_ll.c"

echo
echo "total:"
du -sh "$D"
find "$D" -name '*.c' | wc -l
