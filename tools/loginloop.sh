#!/bin/sh
# Reintenta el login serie hasta que RouterOS acepte (rc=0) o se agoten.
i=1
while [ $i -le 12 ]; do
	echo "=== intento $i $(date) ==="
	MSYS_NO_PATHCONV=1 python -u tools/rosconsole.py \
		--cmd '/system license print' \
		--cmd '/system resource print' \
		--cmd '/interface print'
	rc=$?
	echo "rc=$rc"
	[ $rc -eq 0 ] && exit 0
	i=$((i + 1))
	sleep 20
done
echo "=== login no confirmado tras 12 intentos ==="
exit 2
