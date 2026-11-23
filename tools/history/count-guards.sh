#!/bin/bash
F=/opt/ros-port/linux-5.6.3/drivers/net/ethernet/lantiq/xrx500-cbm.c
echo "guard:        $(grep -c 'guard(' "$F")"
echo "scoped_guard: $(grep -c 'scoped_guard' "$F")"
echo "CLASS:        $(grep -c 'CLASS(' "$F")"
echo "no_free_ptr:  $(grep -c 'no_free_ptr' "$F")"
echo "--- lineas ---"
grep -n 'guard(\|scoped_guard\|CLASS(\|no_free_ptr' "$F" | head -12
