# Troubleshooting

Orden recomendado: **consola → U-Boot → TFTP → kernel → NAND/UBI → rootfs →
RouterOS**. Si falla algo, mira primero el último mensaje que sí aparece; el
error visible suele ser varios pasos posterior a la causa.

## Consola y U-Boot

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Nada en consola | Puerto/baudios incorrectos, cable, placa apagada | `ED500_PORT` correcto, 115200 8N1, comprobar `ROM VER` al encender |
| `ROM VER` en bucle | La imagen no entra por la entry esperada | Usar `out/uImage-563`; load/entry `0x80500000` |
| No se caza `grx500 #` | U-Boot autoarranca antes de mandar CR | Aumentar la ventana del cazador; apagar/encender con el cazador ya escuchando |
| `Bad Magic Number` | Se cargó un ELF o un fichero corrupto | Cargar `uImage-563` con `bootm`, no `bootelf` |
| El cazador dice `COM4 ocupado` | Otra consola, Tftpd64 o un cazador anterior tiene el puerto | Cerrar el otro proceso; en Linux, comprobar `fuser`/`lsof` |

El cazador fija `ipaddr 192.168.1.1` y `serverip` a la IP del PC. Si tu red es
distinta, pásale `--pc-ip`; U-Boot debe estar en `192.168.1.1` o ajustar el
script.

## TFTP

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `TFTP error` / timeout | Firewall de Windows, IP equivocada, puerto ocupado | Permitir Python en red privada; probar 69 y 6969; `setenv tftpdstp` |
| `Bytes transferred` con tamaño distinto | El fichero cambió durante la transferencia | Parar el cazador, reconstruir y repetir |
| `Retry count exceeded` | No hay ruta PC↔ED500 | Misma LAN, IP del PC correcta, cable en `lan1..lan4` |
| La transferencia va a 0 | `catch_final.py` no está en la raíz del repo | Ejecutarlo desde `routeros-port`; sirve `out/` |

## Kernel

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `Linux version` no aparece | `bootm` mudo, entry incorrecta o imagen truncada | Verificar `uImage-563` y el log de TFTP; no cargar en `0x82000000` |
| Cuelga tras `MIPS: machine is...` | Frecuencia/reloj o GIC mal en el DTB | Revisar `CPU_HZ`/CGU y el DTB; usar la imagen que ya arrancó |
| `Kernel panic` al arrancar el rootfs | Init/overlay/UBI no disponible | Ver secciones siguientes; consola y `dmesg` |
| `Attempted to kill init` | El shell/init de inspección salió y era PID 1 | No usar `switch_root` con un shell; el init actual usa `chroot` |
| `Demo license expired` | La NAND no es un disco MikroTik | Es el comportamiento esperado; no hay bypass en este repo |

## NAND y UBI

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `No such device` al montar `ubi0:rootfs_0` | UBI no está adjunta o el volumen no existe | `cat /proc/mtd`; `ubiattach -m 1 -d 0`; mirar `/sys/class/ubi` |
| `ecc unrecoverable error` | ECC distinto al usado al escribir la UBI stock | **BCH-4**, no BCH-8; comprobar DTB y bootargs |
| No aparece `/dev/mtd*` | Driver NAND no probeó o DTB incorrecto | `dmesg \| grep -i nand`; verificar `MTD_NAND_LANTIQ_XRX500` y DTS |
| `Bad block table` no aparece | Falta `nand-on-flash-bbt` o el chip no se detectó | Comprobar DTB; no forzar BBT a mano |
| `mkdir /newroot/merged/rw` falla | El rootfs tiene rutas/symlinks que no existen en el overlay | Aviso no fatal; el init continúa |
| `mount: invalid argument` en UBIFS | Geometría/ECC/volumen incorrectos | No escribir; revisar PEB/LEB y el volumen real |

El detalle de geometría y las comprobaciones están en
**[NAND-UBI.md](NAND-UBI.md)**.

## RouterOS

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `Unknown symbol` al cargar `packet_hook`/`switch`/`bridge2` | Faltan símbolos del *fastpath* binario de MikroTik | No es un fallo de build; no hay driver GPL para el GSWIP |
| `phy_helper: Unknown symbol ...` | Módulo propietario con dependencias que el kernel no exporta | Igual: no se puede completar solo con fuentes GPL |
| `getHardwareID: could not get disk /dev/mtdblock0` | RouterOS busca un disco MikroTik, no la NAND Adamo | Esperado; el chequeo de licencia demo falla |
| `Demo license expired!` | Sin licencia MikroTik válida para este hardware | No hay método de bypass; se necesita licencia |
| `applet not found` al usar el shell | BusyBox decide el applet por `argv[0]` | Copiarlo como `busybox`; el init ya lo hace |
| `Overlayfs: upper fs does not support xattr` | El upper es tmpfs sin xattr | Aviso; se pierde index/metacopy, no impide montar |

La red de RouterOS no se arregla con `insmod`: sus módulos esperan el *fastpath*
de MikroTik y un driver para *sus* switches. El kernel de este repo sí tiene
Ethernet Linux (DSA/GSWIP), que es lo que se usa para TFTP y diagnóstico.

## Build

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `build-563.sh` falla en `olddefconfig` | Falta una dependencia o el árbol está incompleto | Ver `/opt/olddef.log`; ejecutar el bootstrap `01…04` |
| `CONFIG FALLO: ...` | La opción no existe en este árbol/versión | Revisar el mensaje; no desactivar a ciegas, el script valida el DTB |
| `DTB FALLO: no tiene BCH-4` | `parche_arranque.py` no se aplicó o el DTB es viejo | Ejecutar el build desde la raíz; revisar el parche |
| `mkimage FALLO` | Falta `u-boot-tools` | `sudo apt install u-boot-tools` |
| `rootfs FALLO` | No existe `ros/rootfs.squashfs` | Extraerlo del `.npk` oficial; ver BOOT/BUILD |
| `endianness` incorrecta | Se compiló little-endian | El target es **mipsbe**; no cambiar el endianness |

## Recuperación

- Si el arranque por TFTP falla, **apaga y enciende**: el firmware original de
  la NAND sigue ahí y arranca solo si no hay cazador.
- No escribas NAND para “arreglar” un fallo de arranque. El método de este repo
  es RAM.
- Para un reseteo remoto, usa `uboot_cycle.py`; si la placa está en Linux, el
  reset por RCU evita depender de `reboot`.
- Guarda el log completo (`logs/try563_v2.log`, `logs/uboot_cycle.log`) antes de
  pedir ayuda, pero **redacta IPs, MACs y números de serie**.
