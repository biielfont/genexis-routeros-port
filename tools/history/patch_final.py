#!/usr/bin/env python3
"""Ultima tanda para dejar compilando el driver en 5.6.3.

  - phylink: el DSA de 5.6.3 usa callbacks por switch (ds, port, ...) en
    dsa_switch_ops; no existe ds->phylink_mac_ops.
  - regmap: la firma del bus es la cruda de 5.6 (reg_buf/val_buf).
  - recortes: tabla rmon, dsa_switch_shutdown, max_num_bridges,
    phylink_get_caps, firmas de vlan.
  - tag provisional DSA_TAG_PROTO_GSWIP hasta portar tag_gswip3.
"""
import pathlib
import re

C = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")
X = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_xrx500.c")


def rsub(s, pattern, new, label, flags=re.S):
    n = len(re.findall(pattern, s, flags))
    if n:
        print(f"ok: {label} ({n})")
        return re.sub(pattern, new, s, flags=flags)
    print(f"NO: {label}")
    return s


def sub(s, old, new, label):
    if old in s:
        print("ok:", label)
        return s.replace(old, new)
    print("NO:", label)
    return s


def main():
    # ================= common.c =================
    c = C.read_text(errors="replace")

    # tabla de histogramas RMON: no existe la estructura en 5.6.3
    c = rsub(c, r"static const struct ethtool_rmon_hist_range gswip_rmon_ranges\[\] = \{.*?\n\};",
             "/* recortado: gswip_rmon_ranges (struct inexistente en 5.6.3) */\n#if 0\nstatic const int gswip_rmon_ranges[] = { 0 };\n#endif", "rmon_ranges")

    # ethtool_puts -> copia fija de 32 bytes
    c = sub(c, "\t\tethtool_puts(&data, gswip_rmon_cnt[i].name);",
            "\t\t{ strscpy((char *)data, gswip_rmon_cnt[i].name, ETH_GSTRING_LEN);"
            "\n\t\t  data += ETH_GSTRING_LEN; }", "ethtool_puts")

    # phylink: no hay ds->phylink_mac_ops
    c = sub(c, "\tpriv->ds->phylink_mac_ops = &gswip_phylink_mac_ops;\n", "", "ds->phylink_mac_ops")

    # max_num_bridges tampoco existe
    c = rsub(c, r"\tif \(priv->hw_info->port_set_fid\)\n\t\tpriv->ds->max_num_bridges = priv->hw_info->max_ports;\n",
             "", "max_num_bridges")

    # vlan_filtering sin extack
    c = sub(c, """static int gswip_port_vlan_filtering(struct dsa_switch *ds, int port,
\t\t\t\t     bool vlan_filtering,
\t\t\t\t     struct netlink_ext_ack *extack)""",
            """static int gswip_port_vlan_filtering(struct dsa_switch *ds, int port,
\t\t\t\t     bool vlan_filtering)""", "vlan_filtering")

    # quitar la tabla phylink_mac_ops (DSA 5.6.3 no la usa)
    c = rsub(c, r"static const struct phylink_mac_ops gswip_phylink_mac_ops = \{.*?\n\};",
             """/* 5.6.3: las callbacks de phylink van en dsa_switch_ops, no aqui. */

static void gswip_phylink_validate(struct dsa_switch *ds, int port,
\t\t\t\t   unsigned long *supported,
\t\t\t\t   struct phylink_link_state *state)
{
\t/* permisivo: el PHY de cada puerto anuncia lo que puede */
\tbitmap_fill(supported, __ETHTOOL_LINK_MODE_MASK_NBITS);
}

static int gswip_phylink_mac_link_state(struct dsa_switch *ds, int port,
\t\t\t\t\tstruct phylink_link_state *state)
{
\treturn -EOPNOTSUPP;
}""", "phylink_mac_ops -> validate")

    # firmas de mac_config/link_down/link_up al estilo 5.6.3 (ds, port, ...)
    c = rsub(c, r"static void gswip_phylink_mac_config\(struct phylink_config \*config,\n\t\t\t\t     unsigned int mode,\n\t\t\t\t     phy_interface_t interface\)",
             "static void gswip_phylink_mac_config(struct dsa_switch *ds, int port,\n\t\t\t\t     unsigned int mode,\n\t\t\t\t     const struct phylink_link_state *state)", "mac_config firma")
    c = rsub(c, r"static void gswip_phylink_mac_link_down\(struct phylink_config \*config,\n\s*unsigned int mode,\n\s*phy_interface_t interface\)",
             "static void gswip_phylink_mac_link_down(struct dsa_switch *ds, int port,\n\t\t\t\t       unsigned int mode,\n\t\t\t\t       phy_interface_t interface)", "mac_link_down firma")
    c = rsub(c, r"static void gswip_phylink_mac_link_up\(struct phylink_config \*config,\n\s*struct phy_device \*phydev,\n\s*unsigned int mode,\n\s*phy_interface_t interface,\n\s*int speed, int duplex\)",
             "static void gswip_phylink_mac_link_up(struct dsa_switch *ds, int port,\n\t\t\t\t     unsigned int mode,\n\t\t\t\t     phy_interface_t interface,\n\t\t\t\t     struct phy_device *phydev)", "mac_link_up firma")

    # dentro de las tres: derivar priv/port del switch
    c = rsub(c, r"\tstruct dsa_port \*dp = dsa_phylink_to_port\(config\);\n\tstruct gswip_priv \*priv = dp->ds->priv;\n\tint port = dp->index;\n",
             "\tstruct gswip_priv *priv = ds->priv;\n", "cuerpo phylink")
    c = c.replace("dsa_port_is_cpu(dp)", "dsa_is_cpu_port(ds, port)")
    c = c.replace("state->interface", "interface")

    # velocidad/duplex/pausa: en 5.6.3 mac_link_up no los recibe; se toman del state
    c = rsub(c, r"\t\tgswip_port_set_speed\(priv, port, speed, interface\);\n\t\tgswip_port_set_duplex\(priv, port, duplex\);",
             "\t\tgswip_port_set_speed(priv, port, SPEED_UNKNOWN, interface);\n"
             "\t\tgswip_port_set_duplex(priv, port, DUPLEX_UNKNOWN);", "speed/duplex")

    # registrar phylink en la tabla de ops
    c = sub(c, "\t.get_sset_count\t\t= gswip_get_sset_count,\n",
            """\t.get_sset_count\t\t= gswip_get_sset_count,
\t.phylink_validate\t= gswip_phylink_validate,
\t.phylink_mac_link_state\t= gswig_phylink_mac_link_state_typo,
""".replace("gswig_phylink_mac_link_state_typo", "gswip_phylink_mac_link_state"), "ops phylink")

    C.write_text(c)

    # ================= xrx500.c =================
    x = X.read_text(errors="replace")

    # regmap: firma cruda de 5.6
    x = rsub(x, r"static int gswip_xrx500_reg_read\(void \*ctx, unsigned int reg, unsigned int \*val\)\n\{\n\t\*val = readl\(\(void __iomem \*\)ctx \+ \(\(unsigned long\)reg << 2\)\);\n\treturn 0;\n\}",
             """static int gswip_xrx500_reg_read(void *ctx, const void *reg_buf,
\t\t\t\t size_t reg_len, void *val_buf, size_t val_len)
{
\tu32 reg = get_unaligned_be32(reg_buf);

\t*(u32 *)val_buf = readl((void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}""", "regmap read crudo")

    x = rsub(x, r"static int gswip_xrx500_reg_write\(void \*ctx, unsigned int reg, unsigned int val\)\n\{\n\twritel\(val, \(void __iomem \*\)ctx \+ \(\(unsigned long\)reg << 2\)\);\n\treturn 0;\n\}",
             """static int gswip_xrx500_reg_write(void *ctx, const void *data, size_t count)
{
\tconst u8 *d = data;
\tu32 reg = get_unaligned_be32(d);
\tu32 val;

\tmemcpy(&val, d + 4, sizeof(val));
\twritel(val, (void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}""", "regmap write crudo")

    # shutdown: no existe en 5.6.3
    x = sub(x, "\tdsa_switch_shutdown(chip->priv.ds);\n",
            "\t/* recortado: dsa_switch_shutdown no existe en 5.6.3 */\n", "dsa_switch_shutdown")

    # phylink_get_caps fuera de la tabla de modelos
    x = rsub(x, r"\n\t\t\.phylink_get_caps = gswip_xrx500_r?_phylink_get_caps,", "", "modelos phylink_get_caps")

    # tag provisional: el driver gswip3 aun no esta portado
    n = x.count("DSA_TAG_PROTO_GSWIP3")
    x = x.replace("DSA_TAG_PROTO_GSWIP3", "DSA_TAG_PROTO_GSWIP")
    print("tag provisional aplicado:", n)

    X.write_text(x)


if __name__ == "__main__":
    main()
