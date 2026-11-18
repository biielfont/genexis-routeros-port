#!/usr/bin/env python3
"""Ajustes finales del conduit CBM para 5.6.3:
   - timer_container_of() -> from_timer()
   - estadisticas dev_sw_netstats_* / dev_core_stats_* (6.x) -> sin efecto
   - C11 para las macros de cleanup.h
"""
import pathlib

F = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/xrx500-cbm.c")
MK = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/Makefile")

SHIM = """
/* 5.6.3 no tiene estas estadisticas por netdev; para el primer arranque no
 * se contabilizan (los contadores propios del driver siguen vivos).
 */
#ifndef dev_sw_netstats_tx_add
#define dev_sw_netstats_tx_add(dev, pkts, bytes)	do { } while (0)
#endif
#ifndef dev_sw_netstats_rx_add
#define dev_sw_netstats_rx_add(dev, pkts, bytes)	do { } while (0)
#endif
#ifndef dev_core_stats_tx_dropped_inc
#define dev_core_stats_tx_dropped_inc(dev)		do { } while (0)
#endif
#ifndef dev_core_stats_rx_dropped_inc
#define dev_core_stats_rx_dropped_inc(dev)		do { } while (0)
#endif
"""


def main():
    s = F.read_text(errors="replace")

    n = s.count("timer_container_of(")
    s = s.replace("timer_container_of(", "from_timer(")
    print("timer_container_of:", n)

    if "dev_sw_netstats_tx_add(dev, pkts, bytes)" not in s:
        # insertar despues del ultimo #include del bloque inicial
        idx = 0
        for line in s.splitlines(True):
            idx += len(line)
            if line.startswith("#include"):
                last = idx
        s = s[:last] + SHIM + s[last:]
        print("shim de stats insertado")
    F.write_text(s)

    m = MK.read_text(errors="replace")
    if "CFLAGS_xrx500-cbm.o" not in m:
        m += """
# cleanup.h usa declaraciones dentro del for (C99/C11)
CFLAGS_xrx500-cbm.o := -std=gnu11
"""
        MK.write_text(m)
        print("Makefile: gnu11 anadido")
    else:
        print("Makefile: ya tenia gnu11")


if __name__ == "__main__":
    main()
