"""H41: sustituye el postdiag por un volcado POST-login.

Motivo: el postdiag anterior hacia `: > /ram/userseq.console` (H27), y H28
demostro que crear ese fichero vacio aborta el login en el acto.  Mientras
haya ROS_POST=1, el propio diagnostico impedia entrar.

Este no toca /ram/userseq.console y no escribe nada en el tty hasta que el
intento de login ya ha pasado, para no interrumpir la sesion.
"""
import io
import sys

RUTA = "init-initramfs.sh"

NUEVO = r'''#!/bin/sh
cd /
exec >/dev/ttyS0 2>&1
trap '' 1 2 15
up() { set -- $(/bin/busybox cat /proc/uptime); echo "${1%%.*}"; }
u0=$(up)
echo "=== H41: observador (sin tocar userseq) up=$u0 ==="
# Nada de : > /ram/userseq.console (H28: aborta el login).
# El login lo intenta el cazador a los ~45 s de bootm.  Este volcado
# espera a up>=150 s: si user ha muerto, /dev/ttyS0 sigue siendo el
# unico camino al serie y aqui se vera si aun transmite.
while [ "$(up)" -lt "$((u0+150))" ]; do /bin/busybox usleep 200000; done
echo "=== H41 up=$(up) ==="
echo "--- user.log ---"
for f in /flash/rw/logs/user.log /flash/rw/user.log /flash/nova/logs/messages; do
	[ -e "$f" ] && { echo "== $f ($(/bin/busybox wc -c < $f) B) =="; /bin/busybox tail -n 80 "$f" 2>&1; }
done
echo "--- panics / logs ---"
/bin/busybox ls -l /flash/nova/logs /flash/rw/logs /flash/rw 2>&1
for f in /flash/nova/logs/panic0.log /flash/nova/logs/panic1.log; do
	[ -s "$f" ] && { echo "=== $f ==="; /bin/busybox tail -n 80 "$f"; }
done
echo "--- procesos ---"
/bin/busybox ps
echo "--- estado/wchan de user/parser/login ---"
for p in /proc/[0-9]*; do
	c=$(/bin/busybox tr -d '\0' < $p/cmdline 2>/dev/null)
	case "$c" in
	*user*|*parser*|*login*|*console*)
		echo "PID ${p#/proc/} [$c]"
		/bin/busybox grep -E 'State|SigQ|SigPnd|ShdPnd' $p/status 2>/dev/null
		echo "  wchan: $(/bin/busybox cat $p/wchan 2>/dev/null)"
		echo "  fds: $(/bin/busybox ls -l $p/fd 2>/dev/null | /bin/busybox tr '\n' ' ')"
		;;
	esac
done
echo "--- sockets unix ---"
/bin/busybox cat /proc/net/unix 2>&1 | /bin/busybox grep -E 'userseq|conssock|novasock|logsocket'
echo "=== H41 fin ==="
exit 0
'''


def main():
    src = io.open(RUTA, encoding="utf-8").read()
    ini = src.index("cat > $R/bin/postdiag <<'POST'\n")
    ini = src.index("\n", ini) + 1
    fin = src.index("\nPOST\n", ini) + 1
    nuevo = src[:ini] + NUEVO + src[fin:]
    if nuevo == src:
        print("sin cambios")
        return 1
    io.open(RUTA, "w", encoding="utf-8", newline="").write(nuevo)
    print("postdiag H41 escrito (%d bytes de cuerpo)" % len(NUEVO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
