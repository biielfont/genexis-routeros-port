#!/usr/bin/env python3
"""Ultimos ajustes del conduit: stats variadicas, napi con peso, tstats
al estilo 5.6, del_timer_sync y ethtool_puts/sprintf."""
import pathlib
import re

F = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/xrx500-cbm.c")

HEAD = """/* --- adaptaciones para 5.6.3 (port) --- */
#ifndef dev_sw_netstats_tx_add
#define dev_sw_netstats_tx_add(...)		do { } while (0)
#endif
#ifndef dev_sw_netstats_rx_add
#define dev_sw_netstats_rx_add(...)		do { } while (0)
#endif
#ifndef dev_core_stats_tx_dropped_inc
#define dev_core_stats_tx_dropped_inc(...)	do { } while (0)
#endif
#ifndef dev_core_stats_rx_dropped_inc
#define dev_core_stats_rx_dropped_inc(...)	do { } while (0)
#endif
#ifndef ethtool_puts
#define ethtool_puts(data, str)						\\
	do {								\\
		strscpy((char *)(*(data)), (str), ETH_GSTRING_LEN);	\\
		*(data) += ETH_GSTRING_LEN;				\\
	} while (0)
#endif
#ifndef ethtool_sprintf
#define ethtool_sprintf(data, fmt, ...)					\\
	do {								\\
		snprintf((char *)(*(data)), ETH_GSTRING_LEN, fmt,	\\
			 ##__VA_ARGS__);				\\
		*(data) += ETH_GSTRING_LEN;				\\
	} while (0)
#endif
/* --- fin adaptaciones --- */

"""


def main():
    s = F.read_text(errors="replace")

    # quitar el bloque anterior si existe
    s = re.sub(r"/\* 5\.6\.3 no tiene estas estadisticas.*?#endif\n#endif\n#endif\n#endif\n", "", s, flags=re.S)

    # insertar cabecera antes del primer #include
    m = re.search(r"^#include", s, re.M)
    if m and "adaptaciones para 5.6.3 (port)" not in s:
        s = s[:m.start()] + HEAD + s[m.start():]
        print("cabecera insertada")
    else:
        print("cabecera ya presente o sin includes")

    n = s.count("timer_delete_sync(")
    s = s.replace("timer_delete_sync(", "del_timer_sync(")
    print("timer_delete_sync:", n)

    old = "netif_napi_add(ndev, &priv->rx.napi, xrx500_cbm_rx_poll);"
    new = ("netif_napi_add(ndev, &priv->rx.napi, xrx500_cbm_rx_poll,\n"
           "\t\t\tNAPI_POLL_WEIGHT);")
    if old in s:
        s = s.replace(old, new)
        print("ok: napi weight")
    else:
        print("NO: napi")

    old2 = "\tndev->pcpu_stat_type = NETDEV_PCPU_STAT_TSTATS;\n"
    new2 = ("\tndev->tstats = netdev_alloc_pcpu_stats(struct pcpu_sw_netstats);\n"
            "\tif (!ndev->tstats)\n\t\treturn -ENOMEM;\n")
    if old2 in s:
        s = s.replace(old2, new2)
        print("ok: tstats")
    else:
        print("NO: tstats")

    F.write_text(s)


if __name__ == "__main__":
    main()
