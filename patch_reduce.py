#!/usr/bin/env python3
"""Reduce el driver GSWIP XRX500 de 6.18 a lo que 5.6.3 puede compilar.

Primer arranque: switch plano (CPU + lan1..lan4, un FID por puerto).
Se dejan FUERA, para recuperar despues uno a uno:
  - estadisticas ethtool nuevas (eth_mac/ctrl/pause/rmon, eee)
  - flags de bridge por puerto (port_pre_bridge_flags / port_bridge_flags)
  - phylink_get_caps (5.6.3 usa la validacion antigua)
  - hsr
"""
import pathlib
import re
import sys

XR = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr")

DISABLE_COMMON = [
    "gswip_port_setup",
    "gswip_port_pre_bridge_flags",
    "gswip_port_bridge_flags",
    "gswip_phylink_get_caps",
    "gswip_get_eth_mac_stats",
    "gswip_get_eth_ctrl_stats",
    "gswip_get_pause_stats",
    "gswip_get_rmon_stats",
    "gswip_set_mac_eee",
    "gswip_support_eee",
]

DISABLE_XRX = [
    "gswip_xrx500_phylink_get_caps",
    "gswip_xrx500_r_phylink_get_caps",
]

NEW_OPS = """static const struct dsa_switch_ops gswip_switch_ops = {
\t.get_tag_protocol\t= gswip_get_tag_protocol,
\t.setup\t\t\t= gswip_setup,
\t.teardown\t\t= gswip_teardown,
\t.port_enable\t\t= gswip_port_enable,
\t.port_disable\t\t= gswip_port_disable,
\t.port_bridge_join\t= gswip_port_bridge_join,
\t.port_bridge_leave\t= gswip_port_bridge_leave,
\t.port_fast_age\t\t= gswip_port_fast_age,
\t.port_vlan_filtering\t= gswip_port_vlan_filtering,
\t.port_vlan_add\t\t= gswip_port_vlan_add,
\t.port_vlan_del\t\t= gswip_port_vlan_del,
\t.port_stp_state_set\t= gswip_port_stp_state_set,
\t.port_fdb_add\t\t= gswip_port_fdb_add,
\t.port_fdb_del\t\t= gswip_port_fdb_del,
\t.port_fdb_dump\t\t= gswip_port_fdb_dump,
\t.get_strings\t\t= gswip_get_strings,
\t.get_ethtool_stats\t= gswip_get_ethtool_stats,
\t.get_sset_count\t\t= gswip_get_sset_count,
};
"""


def find_def(s, name):
    """Devuelve (inicio, fin) del cuerpo de la funcion `name`."""
    m = re.search(r"^static\s[^\n;]*?\b" + re.escape(name) + r"\s*\(", s, re.M)
    if not m:
        return None
    try:
        i = s.index("{", m.end())
    except ValueError:
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return m.start(), j + 1
    return None


def disable(path, names):
    s = path.read_text(errors="replace")
    done, missing = [], []
    for n in names:
        if f"/* recortado: {n} */" in s:
            done.append(n)
            continue
        r = find_def(s, n)
        if not r:
            missing.append(n)
            continue
        a, b = r
        s = (s[:a] + f"/* recortado: {n} */\n#if 0\n" + s[a:b] +
             "\n#endif\n" + s[b:])
        done.append(n)
    path.write_text(s)
    return done, missing


def replace_ops(path):
    s = path.read_text(errors="replace")
    m = re.search(r"static const struct dsa_switch_ops gswip_switch_ops = \{.*?\n\};",
                  s, re.S)
    if not m:
        return False
    s = s[:m.start()] + NEW_OPS.strip() + s[m.end():]
    path.write_text(s)
    return True


def main():
    d1, m1 = disable(XR / "lantiq_gswip_common.c", DISABLE_COMMON)
    d2, m2 = disable(XR / "lantiq_gswip_xrx500.c", DISABLE_XRX)
    ok = replace_ops(XR / "lantiq_gswip_common.c")
    print("common recortado:", ", ".join(d1) or "-")
    print("xrx500 recortado:", ", ".join(d2) or "-")
    if m1 or m2:
        print("NO encontrados:", ", ".join(m1 + m2))
    print("tabla de ops reescrita:", ok)


if __name__ == "__main__":
    sys.exit(main())
