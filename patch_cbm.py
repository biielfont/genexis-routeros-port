#!/usr/bin/env python3
"""En 5.6.3 platform_driver.remove devuelve int (hasta 5.14 aprox).
Se adaptan las dos funciones .remove del stack CBM del XRX500."""
import pathlib
import re

FILES = [
    pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/cqm/grx500/cbm.c"),
    pathlib.Path("/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/xrx500-cbm.c"),
]


def fix(path, fname):
    s = path.read_text(errors="replace")
    pat = re.compile(r"static void " + re.escape(fname) +
                     r"\(struct platform_device \*pdev\)\n\{", re.S)
    m = pat.search(s)
    if not m:
        print("NO def:", path.name, fname)
        return
    # cambiar firma
    s = s[:m.start()] + s[m.start():m.end()].replace(
        "static void", "static int", 1) + s[m.end():]

    # anadir return 0 antes del cierre de la funcion
    i = m.end() - 1  # posicion de '{'
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                s = s[:j] + "\n\treturn 0;\n" + s[j:]
                break
    path.write_text(s)
    print("ok:", path.name, fname)


def main():
    fix(FILES[0], "cbm_xrx500_remove")
    fix(FILES[1], "xrx500_cbm_remove")


if __name__ == "__main__":
    main()
