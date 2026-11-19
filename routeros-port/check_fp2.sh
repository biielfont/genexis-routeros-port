#!/bin/bash
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
cd "$R" || exit 1
for s in netif_receive_try_fp fast_path_start_xmit register_fast_path \
         skb_bin_alloc_buffer phy_setup custom_packet_hook_rx; do
    echo "=== $s ==="
    found=0
    for f in $(find . -name "*.ko"); do
        if nm -D "$f" 2>/dev/null | grep -qE " T $s\$"; then
            echo "  definido en: $f"
            found=1
        fi
    done
    [ "$found" = 0 ] && echo "  NO lo define ningun modulo"
done
echo
echo "=== modulos misc y net completos ==="
ls lib/modules/5.6.3/misc/ | head -40
