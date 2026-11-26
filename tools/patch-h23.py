"""Parche H23: compila timediag y lo ejecuta antes de sysinit, y cambia el
postdiag por un observador anclado a /proc/uptime (sleep() no duerme).

Se ejecuta desde la raiz del repo: python tools/patch-h23.py
"""
import sys

BS = chr(92)  # barra invertida, para no pelear con el escapado del shell

# --- 1) build-563.sh: compilar timediag tras el bloque de tickfile ---
b = "build-563.sh"
s = open(b, "rb").read().decode("utf-8")
if "bin/timediag" not in s:
    lines = s.split("\n")
    idx = None
    for n, l in enumerate(lines):
        if "initramfs/bin/tickfile" in l and "-o " in l:
            idx = n
            break
    if idx is None:
        sys.exit("no encuentro la linea de tickfile en build-563.sh")
    ins = [
        "# mide si el kernel duerme de verdad (sleep/usleep/nanosleep vs uptime)",
        '${CROSS}gcc -static -O2 -o /opt/ros-port/initramfs/bin/timediag '
        '"$AQUI/tools/timediag.c" ' + BS,
        '  || { echo "timediag FALLO"; exit 1; }',
    ]
    lines[idx + 2:idx + 2] = ins
    open(b, "wb").write("\n".join(lines).encode("utf-8"))
    print("build-563.sh: timediag insertado tras la linea %d" % idx)
else:
    print("build-563.sh: timediag ya estaba")

# --- 2) init-initramfs.sh ---
p = "init-initramfs.sh"
d = open(p, "rb").read().decode("utf-8")

if "/bin/timediag 2>&1" not in d:
    marca = 'echo "  lanzando /sbin/sysinit (switch_root)"'
    k = d.index(marca)
    ini = d.rfind("\n", 0, k) + 1
    indent = d[ini:k]
    ins = (indent + "# El reloj es sospechoso: sleep() vuelve al instante. Se mide antes\n"
           + indent + "# de arrancar sysinit: si el temporizador esta roto, los timeouts\n"
           + indent + "# de RouterOS (login, www, parser) caducan solos al empezar.\n"
           + indent + '/bin/timediag 2>&1 | while read -r L; do echo "  $L"; done\n')
    d = d[:ini] + ins + d[ini:]
    print("init: timediag antes de sysinit")
else:
    print("init: timediag ya estaba")

start = "cat > $R/bin/postdiag <<'POST'\n"
i = d.index(start) + len(start)
j = d.index("\nPOST\n", i)

NEW = '''#!/bin/sh
cd /
# H23: observador de la cadena de arranque, anclado a /proc/uptime.
#   sstore -> /ram/storereg
#   loader -> /ram/novasock   (sysinit lo executa en "Starting services...")
#   log    -> /ram/logsocket  (libumsg conecta a novasock; errno=2 si falta)
#   user   -> espera los tres sockets y arranca
# /bin/busybox sleep vuelve al instante en este kernel (lo mide timediag),
# asi que el retardo se cuenta con /proc/uptime, que si avanza en tiempo
# real: el bucle H22 se comio sus 40 min en once segundos.
if [ -c /dev/ttyLTQ0 ]; then CON=/dev/ttyLTQ0; else CON=/dev/console; fi
exec >$CON 2>&1
trap '' 1 2 15
nodos() {
	for p in /ram/storereg /ram/novasock /ram/logsocket; do
		if [ -e "$p" ]; then /bin/busybox ls -ld "$p"; else echo "missing: $p"; fi
	done
}
up() {
	set -- $(/bin/busybox cat /proc/uptime)
	echo "${1%%.*}"
}
echo
echo "=== H23: inicio ==="
/bin/busybox date
u0=$(up)
prev=""
while [ "$(up)" -lt "$((u0+2700))" ]; do
	m=""
	for p in /ram/storereg /ram/novasock /ram/logsocket; do
		if [ -S "$p" ]; then m="${m}1"; else m="${m}0"; fi
	done
	nb=$(/bin/busybox ps | /bin/busybox grep -c '[/]nova/bin/')
	u=$(up)
	echo "H23 up=${u}s sockets=$m nova=$nb"
	if [ "$m" != "$prev" ]; then
		echo "=== H23: cambio de sockets en up=${u}s ==="
		/bin/busybox date
		nodos
		echo -n "pid1: "; /bin/busybox cat /proc/1/cmdline 2>/dev/null; echo
		/bin/busybox ps
		/bin/busybox cat /proc/net/unix
		echo "=== H23: user.log ==="
		/bin/busybox cat /flash/rw/user.log 2>&1
		prev="$m"
	fi
	t=$((u+30))
	while [ "$(up)" -lt "$t" ]; do /bin/busybox usleep 200000; done
done
echo "=== H23: fin ==="
/bin/busybox ps
nodos
/bin/busybox cat /flash/rw/user.log 2>&1
exit 0'''

d = d[:i] + NEW + d[j:]
d = d.replace('echo "  postdiag: armado (H22, observador periodico 40 min)"',
              'echo "  postdiag: armado (H23, observador anclado a uptime)"')
assert "H23, observador anclado" in d
open(p, "wb").write(d.encode("utf-8"))
print("init: postdiag H23 escrito (%d bytes)" % len(NEW))
