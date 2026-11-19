#!/bin/bash
K=/opt/ros-port/linux-5.6.3
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
echo "=== MODVERSIONS / MODULE_SIG del kernel ==="
grep -E "^CONFIG_(MODVERSIONS|MODULE_SIG|MODULE_FORCE_LOAD|MODULE_UNLOAD)" "$K/.config"
echo
echo "=== flash.ko: licencia y depends ==="
modinfo "$R/lib/modules/5.6.3/misc/flash.ko" | grep -E "^(license|depends|vermagic|name)"
echo
echo "=== simbolos UND de flash.ko ==="
nm -u "$R/lib/modules/5.6.3/misc/flash.ko" 2>/dev/null | head -40
echo
echo "=== __versions de flash.ko ==="
modinfo -F vermagic "$R/lib/modules/5.6.3/misc/flash.ko"
readelf -S "$R/lib/modules/5.6.3/misc/flash.ko" 2>/dev/null | grep -E "__versions|gnu.linkonce"
