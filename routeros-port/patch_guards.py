#!/usr/bin/env python3
"""Los dos unicos scoped_guard(spinlock_irqsave) se reescriben a mano:
esa variante necesita guardar los flags, y para dos sitios no merece la pena
portar la maquinaria completa de cleanup.h."""
import pathlib

F = pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/xrx500-cbm.c")

A_OLD = """\tscoped_guard(spinlock_irqsave, &xrx500_cbm_tx_lock) {
\t\tforced = priv->force_empty != 0;
\t\tif (forced)
\t\t\tpriv->force_empty--;
\t}"""
A_NEW = """\t{
\t\tunsigned long __flags;

\t\tspin_lock_irqsave(&xrx500_cbm_tx_lock, __flags);
\t\tforced = priv->force_empty != 0;
\t\tif (forced)
\t\t\tpriv->force_empty--;
\t\tspin_unlock_irqrestore(&xrx500_cbm_tx_lock, __flags);
\t}"""

B_OLD = """\tlist_for_each_entry(priv, &xrx500_cbm_conduits, node)
\t\tscoped_guard(spinlock_irqsave, &xrx500_cbm_tx_lock)
\t\t\tpriv->force_empty = tx_force_empty;"""
B_NEW = """\tlist_for_each_entry(priv, &xrx500_cbm_conduits, node) {
\t\tunsigned long __flags;

\t\tspin_lock_irqsave(&xrx500_cbm_tx_lock, __flags);
\t\tpriv->force_empty = tx_force_empty;
\t\tspin_unlock_irqrestore(&xrx500_cbm_tx_lock, __flags);
\t}"""


def main():
    s = F.read_text(errors="replace")
    for old, new, tag in ((A_OLD, A_NEW, "A"), (B_OLD, B_NEW, "B")):
        if old in s:
            s = s.replace(old, new)
            print("ok:", tag)
        else:
            print("NO:", tag)
    F.write_text(s)


if __name__ == "__main__":
    main()
