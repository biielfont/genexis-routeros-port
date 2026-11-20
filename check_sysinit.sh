#!/bin/bash
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
cd "$R" || exit 1
echo "=== dispositivos que abre sysinit ==="
strings -n 5 sbin/sysinit | grep -E "^/dev/(console|tty|mtd|flash)" | sort -u | head -25
echo
echo "=== cadenas alrededor de license en sysinit ==="
strings -n 6 sbin/sysinit | grep -n -i -E "licen|system id|system-id" | head -25
echo
echo "=== posibles mensajes de consola/shell ==="
strings -n 6 sbin/sysinit | grep -i -E "press|any key|shell|login|rescue|safe mode" | head -20
echo
echo "=== tamano y tipo ==="
ls -l sbin/sysinit bin/shell nova/bin/cerm 2>/dev/null
file sbin/sysinit bin/shell 2>/dev/null
