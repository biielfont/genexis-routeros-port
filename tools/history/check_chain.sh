#!/bin/bash
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
K=/opt/ros-port/linux-5.6.3
cd "$R" || exit 1
echo "=== packet_hook.ko sin resolver ==="
nm -u lib/modules/5.6.3/drivers/net/packet_hook.ko 2>/dev/null | head -25
echo
echo "=== phy_helper.ko sin resolver ==="
nm -u lib/modules/5.6.3/drivers/net/phy_helper.ko 2>/dev/null | head -25
echo
echo "=== quien define fast_path_start_xmit ==="
for f in $(find . -name "*.ko"); do
    if nm -D "$f" 2>/dev/null | grep -q " T fast_path_start_xmit"; then echo "$f"; fi
done
grep -rln "fast_path_start_xmit" "$K" --include=*.c 2>/dev/null | head -3
echo
echo "=== modules.dep.system (primeras lineas) ==="
head -25 lib/modules/5.6.3/modules.dep.system
