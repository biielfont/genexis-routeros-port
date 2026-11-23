#!/usr/bin/env python3
"""Adapta a la API de 5.6.3 los cuatro puntos que quedan:
   - FID sin struct dsa_bridge
   - firmas de port_bridge_join/leave (net_device *, sin tx_fwd_offload)
   - switchdev_obj_port_vlan: vid -> vid_begin
   - fuera ds->mtu_enforcement_ingress
"""
import pathlib
import re

F = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_common.c")

SUBS = [
    # 1. FID: sin dominio por bridge
    ("""static u16 gswip_port_fid(struct gswip_priv *priv, int port)
{
\tstruct dsa_bridge *bridge = dsa_to_port(priv->ds, port)->bridge;

\tif (bridge)
\t\treturn bridge->num;

\treturn GSWIP_FID_STANDALONE_BASE + port;
}""",
     """static u16 gswip_port_fid(struct gswip_priv *priv, int port)
{
\t/* 5.6.3 no tiene struct dsa_bridge ni un numero de dominio por bridge:
\t * primer arranque con un FID por puerto. El offload de bridge se
\t * recupera cuando el switch plano funcione.
\t */
\t(void)priv;
\treturn GSWIP_FID_STANDALONE_BASE + port;
}"""),

    # 2. join: 5.6.3 pasa el net_device del bridge
    ("""static int gswip_port_bridge_join(struct dsa_switch *ds, int port,
\t\t\t\t  struct dsa_bridge bridge,
\t\t\t\t  bool *tx_fwd_offload,
\t\t\t\t  struct netlink_ext_ack *extack)
{
\tstruct net_device *br = bridge.dev;
\tstruct gswip_priv *priv = ds->priv;""",
     """static int gswip_port_bridge_join(struct dsa_switch *ds, int port,
\t\t\t\t  struct net_device *br,
\t\t\t\t  struct netlink_ext_ack *extack)
{
\tstruct gswip_priv *priv = ds->priv;"""),

    # 3. leave
    ("""static void gswip_port_bridge_leave(struct dsa_switch *ds, int port,
\t\t\t\t    struct dsa_bridge bridge)
{
\tstruct net_device *br = bridge.dev;
\tstruct gswip_priv *priv = ds->priv;""",
     """static void gswip_port_bridge_leave(struct dsa_switch *ds, int port,
\t\t\t\t    struct net_device *br)
{
\tstruct gswip_priv *priv = ds->priv;"""),

    # 4. MTU: el flag no existe en 5.6.3
    ("\tds->mtu_enforcement_ingress = true;\n", ""),
]


def main():
    s = F.read_text(errors="replace")
    for old, new in SUBS:
        if old not in s:
            print("NO ENCONTRADO:", old.splitlines()[0][:60])
            continue
        s = s.replace(old, new, 1)

    # 5. VLAN: 5.6.3 usa vid_begin/vid_end
    s, n = re.subn(r"\bvlan->vid\b", "vlan->vid_begin", s)
    print("vlan->vid cambiados:", n)

    F.write_text(s)
    print("parche aplicado")


if __name__ == "__main__":
    main()
