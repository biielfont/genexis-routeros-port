# H19: escribir por la consola real (ttyLTQ0), no por logring.
if [ -c /dev/ttyLTQ0 ]; then CON=/dev/ttyLTQ0; else CON=/dev/console; fi
exec >$CON 2>&1
echo
echo "=== H19: inicio (consola $CON) ==="
# Espera a que sysinit cree storereg o a agotar vueltas (el reloj de la
# placa corre rapido, por eso se cuenta con vueltas y no con segundos).
i=0
while [ $i -lt 1200 ]; do
	[ -S /ram/storereg ] && break
	/bin/busybox sleep 1
	i=$((i+1))
done
echo "=== H19: espera terminada (vueltas=$i) ==="
/bin/busybox ps
echo "=== H19: /ram ==="
/bin/busybox ls -l /ram/
echo "=== H19: sockets unix ==="
/bin/busybox cat /proc/net/unix
echo "=== H19: procesos /nova/bin ==="
for d in /proc/[0-9]*; do
	p=${d#/proc/}
	c=$(/bin/busybox cat $d/cmdline 2>/dev/null | /bin/busybox tr '\000' ' ')
	case "$c" in
		*nova/bin*)
			echo "--- pid $p: $c"
			/bin/busybox head -n 5 $d/status 2>/dev/null
			echo "wchan: $(/bin/busybox cat $d/wchan 2>/dev/null)"
			echo "syscall: $(/bin/busybox cat $d/syscall 2>/dev/null)"
			/bin/busybox ls -l $d/fd 2>/dev/null | /bin/busybox head -n 12
			;;
	esac
done
echo "=== H19: lanzo loader con salida a $CON ==="
( /nova/bin/loader </dev/null >$CON 2>&1 ) &
/bin/busybox sleep 20
echo "=== H19: estado de loader ==="
for p in $(/bin/busybox pidof loader); do
	echo "--- loader pid $p"
	/bin/busybox head -n 5 /proc/$p/status 2>/dev/null
	echo "wchan: $(/bin/busybox cat /proc/$p/wchan 2>/dev/null)"
	echo "syscall: $(/bin/busybox cat /proc/$p/syscall 2>/dev/null)"
	/bin/busybox ls -l /proc/$p/fd 2>/dev/null
	echo "children: $(/bin/busybox cat /proc/$p/task/$p/children 2>/dev/null)"
done
echo "=== H19: nodos /ram al final ==="
for p in /ram/storereg /ram/novasock /ram/logsocket; do
	if [ -e "$p" ]; then /bin/busybox ls -ld "$p"; else echo "missing: $p"; fi
done
echo "=== H19: fin ==="
exit 0
