#!/bin/bash
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
cd "$R" || exit 1
for f in lib/modules/5.6.3/misc/jiffies.ko \
         lib/modules/5.6.3/misc/lcd.ko \
         lib/modules/5.6.3/drivers/net/packet_hook.ko \
         lib/modules/5.6.3/drivers/net/phy_helper.ko \
         lib/modules/5.6.3/drivers/net/switch.ko \
         lib/modules/5.6.3/net/bridge/bridge2.ko; do
    printf '%-58s ' "$f"
    if [ -f "$f" ]; then
        printf 'existe  '
        modinfo "$f" 2>/dev/null | grep -E '^(license|vermagic)' | tr '\n' ' '
        echo
    else
        echo "NO EXISTE"
    fi
done
echo
echo "=== simbolos sin resolver de switch.ko ==="
nm -u lib/modules/5.6.3/drivers/net/switch.ko 2>/dev/null | head -30
echo
echo "=== simbolos sin resolver de bridge2.ko ==="
nm -u lib/modules/5.6.3/net/bridge/bridge2.ko 2>/dev/null | head -20
echo
echo "=== hay modules.dep? ==="
ls lib/modules/5.6.3/ | head
