#!/usr/bin/env python3
"""Tercera tanda: lo que cambia de fondo, no solo de nombre.

  1. regmap: 5.6.3 no tiene reg_shift; se implementa un bus con el
     desplazamiento del XRX500 (direccion = reg << 2).
  2. phylink: 5.6.3 usa mac_config(config, mode, interface) y
     mac_link_up sin argumentos de pausa; sin lpi ni select_pcs.
  3. firmas de ops: bridge_join y vlan_filtering sin extack,
     vlan_add devuelve void.
"""
import pathlib
import re

C = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")
X = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_xrx500.c")


def sub(s, old, new, label, count=1):
    if old in s:
        print("ok:", label)
        return s.replace(old, new, count)
    print("NO:", label)
    return s


def main():
    # ---------- 1. regmap ----------
    x = X.read_text(errors="replace")
    x = sub(x, """static const struct regmap_config gswip_xrx500_regmap_config = {
\t.name = "switch",
\t.reg_bits = 32,
\t.val_bits = 32,
\t.reg_shift = REGMAP_UPSHIFT(2),
\t.val_format_endian = REGMAP_ENDIAN_LITTLE,
\t.max_register = GSWIP_XRX500_MAX_REGISTER,
};""",
            """/* 5.6.3 no tiene reg_shift: las direcciones del XRX500 van desplazadas
 * dos bits, asi que el acceso se hace a mano sobre el bus de regmap.
 */
static int gswip_xrx500_reg_read(void *ctx, unsigned int reg, unsigned int *val)
{
\t*val = readl((void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}

static int gswip_xrx500_reg_write(void *ctx, unsigned int reg, unsigned int val)
{
\twritel(val, (void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}

static const struct regmap_bus gswip_xrx500_regmap_bus = {
\t.read = gswip_xrx500_reg_read,
\t.write = gswip_xrx500_reg_write,
};

static const struct regmap_config gswip_xrx500_regmap_config = {
\t.name = "switch",
\t.reg_bits = 32,
\t.val_bits = 32,
\t.val_format_endian = REGMAP_ENDIAN_LITTLE,
\t.max_register = GSWIP_XRX500_MAX_REGISTER,
};""", "regmap config")

    x = sub(x, """priv->gswip = devm_regmap_init_mmio(dev, base,""",
            """priv->gswip = devm_regmap_init(dev, &gswip_xrx500_regmap_bus, base,""",
            "regmap init")
    X.write_text(x)

    # ---------- 2 y 3. common ----------
    c = C.read_text(errors="replace")

    # mac_config: 5.6.3 pasa la interfaz, no el estado
    c = sub(c, """static void gswip_phylink_mac_config(struct phylink_config *config,
\t\t\t\t     unsigned int mode,
\t\t\t\t     const struct phylink_link_state *state)""",
            """static void gswip_phylink_mac_config(struct phylink_config *config,
\t\t\t\t     unsigned int mode,
\t\t\t\t     phy_interface_t interface)""", "mac_config firma")
    c = c.replace("state->interface", "interface")

    # mac_link_up: sin pausa (llego en 5.10)
    c = sub(c, """static void gswip_phylink_mac_link_up(struct phylink_config *config,
\t\t\t\t      struct phy_device *phydev,
\t\t\t\t      unsigned int mode,
\t\t\t\t      phy_interface_t interface,
\t\t\t\t      int speed, int duplex,
\t\t\t\t      bool tx_pause, bool rx_pause)""",
            """static void gswip_phylink_mac_link_up(struct phylink_config *config,
\t\t\t\t      struct phy_device *phydev,
\t\t\t\t      unsigned int mode,
\t\t\t\t      phy_interface_t interface,
\t\t\t\t      int speed, int duplex)""", "mac_link_up firma")
    c = sub(c, "\t\tgswip_port_set_pause(priv, port, tx_pause, rx_pause);\n", "", "set_pause")

    # phylink ops: fuera lpi y select_pcs
    c = sub(c, """static const struct phylink_mac_ops gswip_phylink_mac_ops = {
\t.mac_config\t\t= gswip_phylink_mac_config,
\t.mac_link_down\t\t= gswip_phylink_mac_link_down,
\t.mac_link_up\t\t= gswip_phylink_mac_link_up,
\t.mac_disable_tx_lpi\t= gswip_phylink_mac_disable_tx_lpi,
\t.mac_enable_tx_lpi\t= gswip_phylink_mac_enable_tx_lpi,
\t.mac_select_pcs\t\t= gswip_phylink_mac_select_pcs,
};""",
            """static const struct phylink_mac_ops gswip_phylink_mac_ops = {
\t.mac_config\t\t= gswip_phylink_mac_config,
\t.mac_link_down\t\t= gswip_phylink_mac_link_down,
\t.mac_link_up\t\t= gswip_phylink_mac_link_up,
};""", "phylink ops")

    # firmas de ops
    c = sub(c, """static int gswip_port_bridge_join(struct dsa_switch *ds, int port,
\t\t\t\t  struct net_device *br,
\t\t\t\t  struct netlink_ext_ack *extack)""",
            """static int gswip_port_bridge_join(struct dsa_switch *ds, int port,
\t\t\t\t  struct net_device *br)""", "bridge_join firma")

    c, n = re.subn(r"static int gswip_port_vlan_filtering\(struct dsa_switch \*ds, int port,\s*\n\s*bool vlan_filtering, struct netlink_ext_ack \*extack\)",
                   "static int gswip_port_vlan_filtering(struct dsa_switch *ds, int port,\n\t\t\t\t     bool vlan_filtering)", c)
    print("vlan_filtering firma:", n)

    c, n = re.subn(r"static int gswip_port_vlan_add\(struct dsa_switch \*ds, int port,\s*\n\s*const struct switchdev_obj_port_vlan \*vlan,\s*\n\s*struct netlink_ext_ack \*extack\)",
                   "static void gswip_port_vlan_add(struct dsa_switch *ds, int port,\n\t\t\t\tconst struct switchdev_obj_port_vlan *vlan)", c)
    print("vlan_add firma:", n)

    C.write_text(c)


if __name__ == "__main__":
    main()
