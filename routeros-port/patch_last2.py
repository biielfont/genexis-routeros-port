#!/usr/bin/env python3
"""Ultimos 4 errores: variable equivocada en dos funciones y vlan_prepare."""
import pathlib

C = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")


def main():
    c = C.read_text(errors="replace")

    # 1. gswip_mii_delay_setup(priv, dp, interface): recibe la interfaz, no el state
    old = ("\tif (priv->hw_info->mii_pcdu[dp->index] == -1)\n\t\treturn;\n"
           "\n\t/* legacy code to set default delays according to the interface mode */\n"
           "\tswitch (state->interface) {")
    new = ("\tif (priv->hw_info->mii_pcdu[dp->index] == -1)\n\t\treturn;\n"
           "\n\t/* legacy code to set default delays according to the interface mode */\n"
           "\tswitch (interface) {")
    if old in c:
        c = c.replace(old, new)
        print("ok: delay_setup interface")
    else:
        print("NO: delay_setup")

    # 2. mac_config: usa state y ds, no dp
    old2 = ('\t\tdev_err(dp->ds->dev,\n\t\t\t"Unsupported interface: %d\\n", interface);')
    new2 = ('\t\tdev_err(ds->dev,\n\t\t\t"Unsupported interface: %d\\n", state->interface);')
    if old2 in c:
        c = c.replace(old2, new2)
        print("ok: mac_config dev_err")
    else:
        print("NO: mac_config dev_err")

    # 3. vlan_prepare sin extack
    old3 = ("static int gswip_port_vlan_prepare(struct dsa_switch *ds, int port,\n"
            "\t\t\t\t   const struct switchdev_obj_port_vlan *vlan,\n"
            "\t\t\t\t   struct netlink_ext_ack *extack)")
    new3 = ("static int gswip_port_vlan_prepare(struct dsa_switch *ds, int port,\n"
            "\t\t\t\t   const struct switchdev_obj_port_vlan *vlan)")
    if old3 in c:
        c = c.replace(old3, new3)
        print("ok: vlan_prepare firma")
    else:
        print("NO: vlan_prepare firma")

    C.write_text(c)


if __name__ == "__main__":
    main()
