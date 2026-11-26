# H20: consola real y arranque del daemon `log` (crea /ram/logsocket).
if [ -c /dev/ttyLTQ0 ]; then CON=/dev/ttyLTQ0; else CON=/dev/console; fi
exec >$CON 2>&1
echo
echo "=== H20: inicio ==="
i=0
while [ $i -lt 1200 ]; do
	[ -S /ram/storereg ] && break
	/bin/busybox sleep 1
	i=$((i+1))
done
echo "=== H20: storereg tras $i vueltas ==="
/bin/busybox ps
# Lanzar log varias veces: si muere, se vuelve a lanzar para que quede
# rastro del fallo en serie (connect failed, signal 6, ...) y asi poder
# razonar la cadena de sockets con un solo arranque.
L=0
while [ $L -lt 3 ]; do
	echo
echo "=== H20: lanzo /nova/bin/log (intento $((L+1))) ==="
( /nova/bin/log </dev/null >$CON 2>&1 ) &
LP=$!
M=0
while [ $M -lt 15 ]; do
	/bin/busybox kill -0 $LP 2>/dev/null && break
	/bin/busybox sleep 1
	M=$((M+1))
done
if ! /bin/busybox kill -0 $LP 2>/dev/null; then
	echo "=== H20: log muerto tras ${M}s (intentos: $L) ==="
fi
L=$((L+1))
done
j=0
while [ $j -lt 300 ]; do
	[ -S /ram/logsocket ] && break
	/bin/busybox sleep 1
	j=$((j+1))
done
echo "=== H20: logsocket tras $j vueltas ==="
for p in /ram/storereg /ram/novasock /ram/logsocket; do
	if [ -e "$p" ]; then /bin/busybox ls -ld "$p"; else echo "missing: $p"; fi
done
echo "=== H20: procesos ==="
/bin/busybox ps
echo "=== H20: unix ==="
/bin/busybox cat /proc/net/unix
echo "=== H20: espero 200 vueltas mas ==="
/bin/busybox sleep 200
echo "=== H20: procesos finales ==="
/bin/busybox ps
echo "=== H20: nodos finales ==="
for p in /ram/storereg /ram/novasock /ram/logsocket; do
	if [ -e "$p" ]; then /bin/busybox ls -ld "$p"; else echo "missing: $p"; fi
done
echo "=== H20: user.log ==="
/bin/busybox cat /flash/rw/user.log 2>&1
echo "=== H20: fin ==="
exit 0
