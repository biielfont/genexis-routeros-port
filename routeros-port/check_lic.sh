#!/bin/bash
R="$(cd "$(dirname "$0")" && pwd)/ros/rootfs"
cd "$R" || exit 1
for f in nova/bin/cerm nova/bin/loader sbin/sysinit bin/shell; do
    echo "=== $f ==="
    strings -n 6 "$f" 2>/dev/null | grep -i "demo licen" | head -5
done
echo
echo "=== fichero etc/license ==="
ls -l etc/license
head -c 200 etc/license | od -c | head -6
