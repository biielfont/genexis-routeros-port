#!/bin/bash
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
cd "$R" || exit 1
echo "=== ficheros con licen en el nombre ==="
find . -iname "*licen*" 2>/dev/null | head -20
echo
echo "=== quien contiene 'Software ID' ==="
for f in $(find nova/bin sbin bin -type f 2>/dev/null); do
    if strings -n 6 "$f" 2>/dev/null | grep -q "Software ID"; then
        echo "  $f"
    fi
done
echo
echo "=== cadenas 'Software ID' y alrededores en sysinit ==="
strings -n 4 sbin/sysinit | grep -n -B4 -A4 "Software" | head -30
echo
echo "=== sysinit: cadenas de licencia completas ==="
strings -n 4 sbin/sysinit | grep -n -i -E "licen|demo|expire|upgrade" | head -30
