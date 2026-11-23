#!/usr/bin/env python3
"""Los 3 ultimos: extack en el mensaje de VLAN y la llamada a delay_setup."""
import pathlib

C = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")


def main():
    c = C.read_text(errors="replace")

    old = '\t\t\tNL_SET_ERR_MSG_MOD(extack, "No slot in VLAN table");'
    new = '\t\t\tdev_err(ds->dev, "No slot in VLAN table\\n");'
    if old in c:
        c = c.replace(old, new)
        print("ok: NL_SET_ERR_MSG_MOD")
    else:
        print("NO: NL_SET_ERR_MSG_MOD")

    old2 = "\tgswip_mii_delay_setup(priv, dp, interface);"
    new2 = ("\tgswip_mii_delay_setup(priv, dsa_to_port(ds, port),\n"
            "\t\t\t       state->interface);")
    if old2 in c:
        c = c.replace(old2, new2)
        print("ok: delay_setup call")
    else:
        print("NO: delay_setup call")

    C.write_text(c)


if __name__ == "__main__":
    main()
