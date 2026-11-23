#!/bin/bash
R=/mnt/c/Users/BFR/Documents/Genexis/routeros-port/ros/rootfs
cd "$R" || exit 1
echo "=== ficheros early/shell en el rootfs ==="
find . -name "*early*" -o -name "*shell*" -o -name "*rescue*" 2>/dev/null | head -20
echo
echo "=== cadenas de sysinit: contexto de early_shell ==="
strings -n 4 sbin/sysinit | grep -n -B6 -A6 "early_shell" | head -30
echo
echo "=== cadenas de sysinit: ruta /flash/ ==="
strings -n 6 sbin/sysinit | grep -E "/flash/" | head -20
echo
echo "=== posibles argumentos ==="
strings -n 3 sbin/sysinit | grep -E "^(start|stop|restart|early|shell|boot|halt|reboot|upgrade|check)" | head -25
echo
echo "=== bin/ y sbin/ del rootfs ==="
ls bin/ | head -40
