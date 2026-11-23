#!/usr/bin/env python3
"""Repara el dano del parche anterior (return 0; dentro de of_match) y
termina los dos simbolos que faltan."""
import pathlib

F = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/xrx500-cbm.c")


def main():
    s = F.read_text(errors="replace")

    bad = """static const struct of_device_id xrx500_cbm_of_match[] = {
\t{ .compatible = "lantiq,xrx500-conduit" 
\treturn 0;
},
\t{ }
};"""
    good = """static const struct of_device_id xrx500_cbm_of_match[] = {
\t{ .compatible = "lantiq,xrx500-conduit" },
\t{ }
};"""
    if bad in s:
        s = s.replace(bad, good)
        print("ok: tabla of_match reparada")
    else:
        print("NO: tabla of_match (revisar a mano)")

    # el return de remove, donde toca
    bad2 = """\tfree_netdev(priv->ndev);
}

static const struct of_device_id xrx500_cbm_of_match[]"""
    good2 = """\tfree_netdev(priv->ndev);
\treturn 0;
}

static const struct of_device_id xrx500_cbm_of_match[]"""
    if bad2 in s:
        s = s.replace(bad2, good2)
        print("ok: return de remove")
    else:
        print("NO: return de remove")

    n = s.count("timer_shutdown_sync(")
    s = s.replace("timer_shutdown_sync(", "del_timer_sync(")
    print("timer_shutdown_sync:", n)

    F.write_text(s)


if __name__ == "__main__":
    main()
