#!/usr/bin/env python3
"""El simbolo NET_DSA_XR_GSWIP vive en drivers/net/dsa/Kconfig (el directorio xr
no tiene Kconfig propio). Le anadimos el select del tag nuevo y borramos el
tag_gswip3.c suelto de xr/ que no compila nadie (era un intento viejo)."""
import os

P = "/opt/ros-port/linux-5.6.3/drivers/net/dsa/Kconfig"
s = open(P).read()

if "NET_DSA_TAG_GSWIP3" in s:
    print("select ya estaba")
else:
    old = "config NET_DSA_XR_GSWIP\n"
    i = s.index(old)
    j = i + len(old)
    # meter el select justo despues de la linea del symbol
    s = s[:j] + "\tselect NET_DSA_TAG_GSWIP3\n" + s[j:]
    open(P, "w").write(s)
    print("select anadido")

stray = "/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/tag_gswip3.c"
if os.path.exists(stray):
    os.remove(stray)
    print("borrado el tag_gswip3.c suelto de xr/")
