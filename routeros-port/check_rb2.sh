#!/bin/bash
K=/opt/ros-port/linux-5.6.3
cd "$K" || exit 1
echo "=== arch/mips/rb/rb400/spi.c 10-30, 180-230 ==="
sed -n '10,30p;180,230p' arch/mips/rb/rb400/spi.c
echo
echo "=== definicion mips_machgroup ==="
grep -rn "^unsigned long mips_machgroup\|^unsigned long mips_machtype\|mips_machgroup;" arch/mips --include=*.c | head -5
grep -rn "mips_machgroup" arch/mips/kernel/*.c | head -5
echo
echo "=== is_music_lite ==="
sed -n '835,855p' arch/mips/rb/prom.c
