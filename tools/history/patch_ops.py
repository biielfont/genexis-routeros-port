#!/usr/bin/env python3
"""Segunda tanda de recortes a la API de 5.6.3:
   - port_fdb_add/del: sin struct dsa_db
   - port_fdb_dump: firma distinta -> se deja fuera (solo afecta a 'bridge fdb show')
   - CTL1000_PREFER_MASTER -> CTL1000_ENABLE_MASTER
   - REGMAP_UPSHIFT() -> campo reg_shift entero
   - devm_clk_bulk_get_all_enabled -> devm_clk_bulk_get_all
"""
import pathlib
import re

C = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")
X = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_xrx500.c")

FDB_ADD_OLD = """static int gswip_port_fdb_add(struct dsa_switch *ds, int port,
\t\t\t      const unsigned char *addr, u16 vid,
\t\t\t      struct dsa_db db)
{
\tif (db.type != DSA_DB_BRIDGE)
\t\treturn -EOPNOTSUPP;

\treturn gswip_port_fdb(ds, port, db.bridge.dev, addr, vid, true);
}"""

FDB_ADD_NEW = """static int gswip_port_fdb_add(struct dsa_switch *ds, int port,
\t\t\t      const unsigned char *addr, u16 vid)
{
\treturn gswip_port_fdb(ds, port, dsa_to_port(ds, port)->bridge_dev,
\t\t\t      addr, vid, true);
}"""

FDB_DEL_OLD = """static int gswip_port_fdb_del(struct dsa_switch *ds, int port,
\t\t\t      const unsigned char *addr, u16 vid,
\t\t\t      struct dsa_db db)
{
\tif (db.type != DSA_DB_BRIDGE)
\t\treturn -EOPNOTSUPP;

\treturn gswip_port_fdb(ds, port, db.bridge.dev, addr, vid, false);
}"""

FDB_DEL_NEW = """static int gswip_port_fdb_del(struct dsa_switch *ds, int port,
\t\t\t      const unsigned char *addr, u16 vid)
{
\treturn gswip_port_fdb(ds, port, dsa_to_port(ds, port)->bridge_dev,
\t\t\t      addr, vid, false);
}"""


def drop_func(s, name):
    m = re.search(r"^static\s[^\n;]*?\b" + name + r"\s*\(", s, re.M)
    if not m:
        return s, False
    i = s.index("{", m.end())
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    else:
        return s, False
    return s[:m.start()] + f"/* recortado: {name} */\n#if 0\n" + s[m.start():end] + "\n#endif\n" + s[end:], True


def main():
    c = C.read_text(errors="replace")

    for old, new, label in ((FDB_ADD_OLD, FDB_ADD_NEW, "fdb_add"),
                            (FDB_DEL_OLD, FDB_DEL_NEW, "fdb_del")):
        if old in c:
            c = c.replace(old, new, 1)
            print(label, "adaptado")
        else:
            print(label, "NO ENCONTRADO")

    c, ok = drop_func(c, "gswip_port_fdb_dump")
    print("fdb_dump recortado:", ok)

    # quitar la entrada de la tabla de ops
    c = re.sub(r"\n\t\.port_fdb_dump\t\t= gswip_port_fdb_dump,", "", c)
    C.write_text(c)

    x = X.read_text(errors="replace")
    n1 = x.count("CTL1000_PREFER_MASTER")
    x = x.replace("CTL1000_PREFER_MASTER", "CTL1000_ENABLE_MASTER")
    n2 = x.count("REGMAP_UPSHIFT(1)")
    x = x.replace("REGMAP_UPSHIFT(1)", "1")
    n3 = x.count("devm_clk_bulk_get_all_enabled")
    x = x.replace("devm_clk_bulk_get_all_enabled", "devm_clk_bulk_get_all")
    X.write_text(x)
    print(f"ctl1000={n1} regmap_upshift={n2} clk_bulk={n3}")


if __name__ == "__main__":
    main()
