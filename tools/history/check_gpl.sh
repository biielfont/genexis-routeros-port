#!/bin/bash
K=/opt/ros-port/linux-5.6.3
cd "$K" || exit 1
for s in bus_find_device platform_bus_type device_match_name; do
    echo "=== $s ==="
    grep -rn "EXPORT_SYMBOL.*($s)" drivers/ include/ 2>/dev/null | head -3
done
