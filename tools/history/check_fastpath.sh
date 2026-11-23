#!/bin/bash
K=/opt/ros-port/linux-5.6.3
cd "$K" || exit 1
echo "=== fast_path_start_xmit ==="
grep -rn "fast_path_start_xmit" . --include=*.c --include=*.h 2>/dev/null | head -5
echo
echo "=== fast_path_ (cualquiera) ==="
grep -rln "fast_path_" . --include=*.c --include=*.h 2>/dev/null | head -10
echo
echo "=== dev_disable_change ==="
grep -rn "dev_disable_change" . --include=*.c --include=*.h 2>/dev/null | head -5
echo
echo "=== dev_disable_lro ==="
grep -rn "void dev_disable_lro" . --include=*.c --include=*.h 2>/dev/null | head -5
echo
echo "=== configs FASTPATH/HOOK ==="
grep -E "^CONFIG_.*(FASTPATH|FAST_PATH|PACKET_HOOK|MikroTik)" .config
echo
echo "=== Kconfig con fastpath ==="
grep -rln "fastpath\|FASTPATH" --include=Kconfig . 2>/dev/null | head -10
