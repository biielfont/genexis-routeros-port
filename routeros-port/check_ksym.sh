#!/bin/bash
K=/opt/ros-port/linux-5.6.3
cd "$K" || exit 1
echo "=== TRIM_UNUSED_KSYMS ==="
grep -E "^CONFIG_(TRIM_UNUSED_KSYMS|UNUSED_KSYMS_WHITELIST|KALLSYMS)" .config
echo
echo "=== ksymtab en vmlinux ==="
nm vmlinux | grep -E "__ksymtab_(bus_find_device|platform_bus_type|lzo1x_decompress_safe|device_match_name)$"
echo
echo "=== y sin __ksymtab? ==="
nm vmlinux | grep -E " (bus_find_device|platform_bus_type)$"
