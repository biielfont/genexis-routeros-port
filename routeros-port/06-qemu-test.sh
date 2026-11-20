#!/bin/bash
#
# 06-qemu-test.sh - prueba virtual: arranca el kernel en QEMU (malta/I7200) y
# comprueba que llega a la initramfs con la consola funcionando.
#
# Es un 5.6.3 limpio (sin parche de MikroTik) compilado con la MISMA toolchain
# y la MISMA initramfs de busybox que usara el ED500: lo que se valida aqui es
# el userspace, el /init, la consola serie y el enganche del initramfs, no el
# hardware del GRX350 (que QEMU no emula).
#
set -u

K=/opt/ros-port/malta-clean
OUT="$(cd "$(dirname "$0")" && pwd)/out"
LOG=/opt/ros-port/qemu-malta.log

[ -f "$K/vmlinux" ] || { echo "falta $K/vmlinux: compila primero el arbol malta"; exit 1; }

# QEMU no arranca malta con -cpu I7200 (se queda mudo), asi que se usa 24Kc:
# lo que se valida aqui es el userspace, no el modelo de CPU.
echo "== arrancando QEMU (malta, 256M) =="
timeout 90 qemu-system-mips \
	-M malta \
	-cpu 24Kc \
	-m 256M \
	-kernel "$K/vmlinux" \
	-nographic -no-reboot \
	-append "console=ttyS0 panic=1" \
	> "$LOG" 2>&1

rc=$?
echo "qemu termino con rc=$rc (124 = seguia vivo, correcto)"
cp "$LOG" "$OUT/qemu-malta.log" 2>/dev/null

echo
echo "== comprobaciones =="
fail=0
check() {
	if grep -q "$1" "$LOG"; then
		echo "  OK   $2"
	else
		echo "  FALLO $2"
		fail=1
	fi
}

check "Linux version 5.6.3"            "kernel 5.6.3 arranca"
check "Run /init as init process"      "initramfs montada y /init ejecutado"
check "initramfs viva"                 "banner de la initramfs por consola"
check "~ #"                            "shell de busybox interactiva"
check "CPU0 revision"                  "tabla de CPUs del kernel"
check "Freeing unused kernel memory"   "arranque completo del kernel"

echo
if [ "$fail" = 0 ]; then
	echo "RESULTADO: PASS"
else
	echo "RESULTADO: FAIL (ver $LOG)"
fi
exit "$fail"
