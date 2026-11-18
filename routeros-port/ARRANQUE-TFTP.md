# Arrancar el kernel portado en el Genexis Pure ED500

Todo esto es **en RAM**: no se escribe NAND, la flash con el firmware de Genexis
queda intacta. Si algo falla, apagas y arrancas como siempre.

## 1. Qué hay en `out/`

| Fichero | Para qué |
|---|---|
| `uImage` (3,9 MB) | arranque con `bootm` |
| `vmlinux.elf` (30 MB) | arranque con `bootelf` |
| `vmlinux.bin.gz` (2,4 MB) | más rápido de subir por TFTP; se descomprime en el PC |
| `norrland.dtb` | solo por si quieres pasarlo aparte |

Contenido del kernel: `Linux 5.6.3` + plataforma `intel-mips` (GRX350),
DTB `norrland` embebido, busybox estático en el initramfs.

Datos confirmados con el log de tu U-Boot:

- CPU/DDR a **800/800 MHz** (ya fijado en el DTS, `CPU_HZ`).
- Consola **`ttyLTQ0`** a 115200 (el asc de Lantiq no usa `ttyS0`).
- DRAM **224 MiB**, coherente con `mem=224M@512M` → DDR en `0x20000000`,
  que es justo el `PHYS_OFFSET` de la plataforma.

## 2. Servir por TFTP

Desde esta carpeta (Windows, con Python instalado):

```
python tftp-server.py out --port 69
```

Si el 69 está ocupado (Tftpd64 u otro), usa `--port 6969` y en U-Boot
`setenv tftpdstp 6969`.

Averigua la IP del PC que sirve (`ipconfig` en Windows). En WSL con
`networkingMode=mirrored` la IP es la misma que la de Windows.

## 3. U-Boot del ED500 (consola 115200 8N1)

```
setenv ipaddr 192.168.1.10
setenv serverip 192.168.1.100
setenv netmask 255.255.255.0

# opción A: uImage
tftpboot 0x82000000 uImage
bootm 0x82000000

# opción B: ELF (mejor si el bootm se queja de la arquitectura)
tftpboot 0x82000000 vmlinux.elf
bootelf 0x82000000
```

Los argumentos de arranque los pone el DTB embebido
(`console=ttyLTQ0,115200 earlycon mem=224M@512M`), así que no hace falta
`setenv bootargs`. Si quieres forzarlos:

```
setenv bootargs "console=ttyLTQ0,115200 earlycon mem=224M@512M board=norrland"
```

Ojo: `bootm` reubica la imagen a la dirección de carga del ELF (`0x80500000`,
que con `PHYS_OFFSET 0x20000000` es la física `0x20500000`). Cargar en
`0x82000000` es solo el buffer de staging.

## 4. Qué deberías ver

```
[    0.000000] Linux version 5.6.3 ...
[    0.000000] bootconsole [early0] enabled
[    0.000000] CPU0 revision is: 0001a900 (MIPS interAptiv)
[    0.000000] Intel MIPS interAptiv SoC
[    0.000000] Determined physical RAM map: memory: 0e000000 @ 02000000 (usable)
[    0.000000] GIC: using split EOI/confirm mode
...
==================================================
 GRX350 / norrland - initramfs viva (kernel 5.6.3)
==================================================
```

Si llega a `initramfs viva`, el port está vivo en el SoC real y ya solo queda
ir añadiendo periféricos (NAND, switch, PCIe).

## 5. Si no arranca: qué mirar

| Síntoma | Causa probable | Qué cambiar |
|---|---|---|
| Nada en consola | UART mal direccionada | `earlycon=lantiq,0x16600000` en `bootargs` (escribe sin reprogramar el baud, hereda el de U-Boot) |
| La consola arranca y se corta al ceder el testigo a `ttyLTQ0` | el reloj `asc` no es 100 MHz | ajustar `UART_HZ` en el DTS |
| Cuelga tras "Intel MIPS..." | frecuencia de CPU equivocada → GIC/timer | `CPU_HZ` en `norrland.dts` |
| `Bad Magic Number` | `bootm` no acepta la imagen | usar `bootelf` |
| Reinicio inmediato | excepción temprana | arrancar con `earlycon` y `ignore_loglevel` |

La frecuencia real de CPU aparece en el log del U-Boot de Genexis
(`CPU: 800 MHz` o similar) o en `/proc/cpuinfo` del firmware original; con ese
dato se recompila cambiando solo `#define CPU_HZ` en `norrland.dts`.

## 6. Recompilar tras un cambio

```
wsl -d kali-linux -u root -- bash /mnt/c/Users/BFR/Documents/Genexis/routeros-port/04-build-initramfs.sh
wsl -d kali-linux -u root -- bash -c 'cd /opt/ros-port/linux-5.6.3 && make ARCH=mips \
  CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- -j4 vmlinux'
```

Los artefactos de `out/` se regeneran con `05-package.sh`.

## 7. Pruebas virtuales (sin router)

`06-qemu-test.sh` arranca en QEMU un 5.6.3 **limpio** compilado con la misma
toolchain, la misma initramfs y el mismo endianness (big-endian) que el kernel
del ED500, y verifica el userspace de punta a punta:

```
wsl -d kali-linux -u root -- bash /mnt/c/Users/BFR/Documents/Genexis/routeros-port/06-qemu-test.sh

  OK   kernel 5.6.3 arranca
  OK   initramfs montada y /init ejecutado
  OK   banner de la initramfs por consola
  OK   shell de busybox interactiva
  OK   tabla de CPUs del kernel
  OK   arranque completo del kernel
RESULTADO: PASS
```

Qué cubre: que el kernel arranca, que el initramfs se desempaqueta, que `/init`
se ejecuta, que `/dev/console` existe, que busybox (ELF32 MSB estático) corre y
que la consola serie sirve. El log completo queda en `out/qemu-malta.log`.

Qué **no** cubre: QEMU no emula el GRX350 (GIC en `0x12320000`, asc en
`0x16600000`, NAND, switch). La ruta `prom.c`/`irq.c`/`time.c` de
`arch/mips/intel-mips` solo se puede validar en el equipo real; en QEMU se usa
la máquina `malta` con CPU `24Kc` porque `-cpu I7200` (interAptiv) no arranca
en esa máquina.

## 8. Límite conocido del parche GPL de MikroTik

El parche publicado no es autosuficiente: con una configuración completa
(p.ej. `CONFIG_NET_RX_BUSY_POLL=y`) aparecen referencias a
`dev->napi_defer_hard_irqs` y `napi->defer_hard_irqs_count`, campos que son de
mainline 5.10 y que MikroTik tiene en su árbol pero **no** incluye en el parche:

```
net/core/dev.c:6519: error: 'struct net_device' has no member named 'napi_defer_hard_irqs'
```

Para H3 (config completa de RouterOS) hay dos salidas: desactivar
`NET_RX_BUSY_POLL` en la config (el código queda fuera por `#ifdef`) o restaurar
la implementación original de 5.6.3 de `busy_poll_stop()`. La config mínima
actual no toca ese archivo, por eso compila.
