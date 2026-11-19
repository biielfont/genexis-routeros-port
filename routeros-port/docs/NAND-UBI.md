# NAND, UBI y rootfs

La NAND del ED500 es una **Macronix MX30LF1G18AC**: 128 MiB SLC, página de
2 KiB, OOB de 64 B y PEB de 128 KiB. No está rota; el problema histórico era el
init/particiones, no el chip.

## Geometría y decisión de ECC

| Dato | Valor |
|---|---|
| Capacidad | 128 MiB (1 Gbit) |
| Página | 2 KiB |
| OOB | 64 B |
| PEB | 128 KiB |
| LEB UBI | 124 KiB (`126976`) |
| ECC | **BCH-4** |
| BBT | **`nand-on-flash-bbt`** |

La UBI original de Genexis se escribió con **BCH-4**. Si el kernel se configura
con BCH-8, los headers EC/VID de la UBI stock no se pueden leer y el arranque
parece una NAND muerta. Por eso el DTB y el build actual fijan BCH-4, no BCH-8.

El DTB debe contener, como mínimo:

```text
nand-ecc-strength = <0x04>;
nand-on-flash-bbt;
```

y los bootargs deben incluir:

```text
ubi.mtd=ubi
```

`build-563.sh` verifica las tres cosas antes de empaquetar el `uImage`.

## Particiones

| MTD | Nombre | Tamaño | Uso |
|---|---|---|---|
| `mtd0` | `uboot` | 1 MiB | U-Boot; solo lectura |
| `mtd1` | `ubi` | 127 MiB | UBI con el firmware/rootfs |

El init intenta montar `rootfs_0` y `rootfs_1` en **solo lectura** bajo
`/newroot/merged/mnt/`. Si el bootargs no trajo `ubi.mtd=ubi`, el fallback es:

```sh
ubiattach -m 1 -d 0
```

`mtd0` es el bloque de U-Boot; no se toca. `mtdblock0` es la visión cruda de la
NAND, no el `/dev/flash` que espera RouterOS: `flash.ko` registra su propio
dispositivo de caracteres. No crees un symlink manual a `/dev/mtdblock0`.

## Comprobar la NAND desde el shell

Dentro del initramfs o del shell de RouterOS:

```sh
cat /proc/mtd
ls -l /dev/mtd* /dev/mtdblock* /dev/ubi* 2>/dev/null
ubiattach -m 1 -d 0
for d in /sys/class/ubi/ubi0_*; do
  [ -r "$d/name" ] && echo "$(basename "$d"): $(cat "$d/name")"
done
mkdir -p /mnt/rootfs_0
mount -t ubifs -o ro ubi0:rootfs_0 /mnt/rootfs_0
ls /mnt/rootfs_0 | head
```

La UBI stock tiene varios volúmenes; en el log de referencia aparecen
`rootfs_0` y `rootfs_1` (el volumen 3 era `rootfs_1`). No asumas que los índices
son iguales en otra unidad: mira siempre `/sys/class/ubi`.

## Lo que está probado y lo que no

- **Probado:** detección del chip, BBT en las páginas 65472/65408, attach de
  UBI y lectura del rootfs stock; el init monta `rootfs_0`/`rootfs_1` en ro.
- **No probado como escritura:** no hay `ubi write`, `flash_erase` ni
  actualización persistente en este repo. `out/` y el arranque TFTP no escriben
  NAND.
- **No es un disco MikroTik:** RouterOS usa `/dev/mtdblock0` para derivar su
  *software ID*. Aquí contiene el firmware Adamo, así que el chequeo de licencia
  demo falla. Eso no se arregla con ECC ni con particiones.

## Si algún día escribes NAND

No lo hagas sin:

1. un backup completo y verificado (`nanddump` o lectura equivalente);
2. el mapa de particiones y los volúmenes UBI confirmados;
3. una imagen `.y3`/UBIFS construida para **esta** geometría (PEB 128 KiB,
   LEB 124 KiB, página 2 KiB);
4. un plan de recuperación por UART/ROM y el otro banco de arranque sano.

El contenedor `.y3` está investigado en **[FLASH-Y3.md](FLASH-Y3.md)**, pero es
experimental y **no** es el método actual. El método actual es TFTP a RAM.
