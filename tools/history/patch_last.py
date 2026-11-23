#!/usr/bin/env python3
"""Cierra los ultimos errores de compilacion del driver en 5.6.3."""
import pathlib

C = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")
X = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_xrx500.c")


def sub(s, old, new, label):
    if old in s:
        print("ok:", label)
        return s.replace(old, new)
    print("NO:", label)
    return s


def main():
    c = C.read_text(errors="replace")
    c = sub(c, "gswip_port_vlan_filtering(ds, i, false, NULL);",
            "gswip_port_vlan_filtering(ds, i, false);", "llamada vlan_filtering")
    c = sub(c, "err = gswip_port_vlan_prepare(ds, port, vlan, extack);",
            "err = gswip_port_vlan_prepare(ds, port, vlan);", "llamada vlan_prepare")
    c = sub(c, "\tswitch (interface) {", "\tswitch (state->interface) {", "switch interface")
    c = sub(c, 'if (of_property_read_bool(dp->dn, "maxlinear,rmii-refclk-out"))',
            'if (of_property_read_bool(dsa_to_port(ds, port)->dn,\n\t\t\t\t\t  "maxlinear,rmii-refclk-out"))', "dp->dn")
    c = c.replace("\t\tused_interface = interface;", "\t\tused_interface = state->interface;")
    C.write_text(c)

    x = X.read_text(errors="replace")
    x = sub(x, "\t\t.phylink_get_caps = gswip_xrx500_phylink_get_caps,\n", "", "modelo phylink_get_caps")
    # en 5.6.3 platform_driver.remove devuelve int
    x = sub(x, "static void gswip_xrx500_remove(struct platform_device *pdev)",
            "static int gswip_xrx500_remove(struct platform_device *pdev)", "remove firma")
    x = sub(x, """\tdsa_unregister_switch(chip->priv.ds);
\tgswip_xrx500_gphy_release(chip);
}""",
            """\tdsa_unregister_switch(chip->priv.ds);
\tgswip_xrx500_gphy_release(chip);
\treturn 0;
}""", "remove return")
    X.write_text(x)


if __name__ == "__main__":
    main()
