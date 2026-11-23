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

y los bootargs deben incluir el offset del VID header:

```text
ubi.mtd=ubi,2048,30
```

`build-563.sh` verifica las tres cosas antes de empaquetar el `uImage` (para
`ubi.mtd` basta con que aparezca la cadena).

### Por qué el offset es 2048 y no 512

La UBI de fábrica se escribió con el **VID header en 2048**; el log del
firmware original lo confirma: `VID header offset: 2048 (aligned 2048), data
offset: 4096`. El `nand-ecc-step-size = <512>` que exige el BCH-4 hace que el
kernel habilite escrituras por subpágina (`subpage_sft = 2`). Entonces UBI
calcula `hdrs_min_io_size = 2048 >> 2 = 512` y, si el bootargs solo dice
`ubi.mtd=ubi`, espera el VID header en 512. Al leer el EC header de la flash
(que declara 2048) falla con:

```text
ubi0 error: _save_fp_context: bad VID header offset 2048, expected 512
ubi0 error: _save_fp_context: bad EC header
ubi0 error: failed to attach mtd1, error -22
```

No es un fallo de ECC ni de la NAND: es el offset por defecto. Con
`ubi.mtd=ubi,2048,30`, `leb_start` vuelve a alinearse a 4096 y el layout
coincide con el de fábrica. El fallback manual necesita el mismo offset.

## RouterBoot y `/flash` (builds #72–#76)

`flash.ko` no falla porque la NAND esté mal: aborta si no encuentra un MTD
llamado exactamente **`RouterBoot`**. El binario lo confirma:
`get_mtd_device_nm("RouterBoot")` y, si devuelve error, imprime
`bad RouterBoot MTD device` y no crea `/dev/flash`. Sin `/dev/flash`,
`mount none /flash` también devuelve `EINVAL` (22), pero ese no es el único
motivo: `diskd` llama a `mount("none", "/flash", NULL, ...)` y el kernel
rechaza un tipo de filesystem nulo.

La NAND del ED500 es de Genexis y no tiene ese MTD. El build #72 activa
`CONFIG_MTD_MTDRAM` (16 MiB, borrado de 128 KiB) y renombra el dispositivo a
`RouterBoot` en `mtdram.c`. Es **RAM volátil**:

- no lee ni escribe la NAND;
- no interviene en la licencia ni en el *software ID* de RouterOS;
- el contenido de `/flash` se pierde al reiniciar.

En la prueba del build #72 el nombre bastó para pasar el primer control, pero
no para inicializar el driver: RouterOS necesita además un *hard config*
válido en esa flash. Un MTD en blanco no lo tiene, y el driver abortó con
`vmalloc(0xffffffff)`. El build #73 escribe antes de `sysinit` un **hard
config sintético** en el MTD RAM: cabecera RouterBoot y bloque `Hard` con
product ID 000, MAC real `34:e3:80:c3:77:f0` y serial `W.3620220010`. Es identidad de hardware inventada para esta placa, no un
bypass de licencia, y no toca la NAND. El build #76 añade el bloque `Soft`
(magic `74666f53`) en `0x8000`; el init verifica `magics: hard=64726148
soft=74666f53` y `flash.ko` ya no aborta: registra `/dev/flash`. La NAND real
sigue intacta y sin escrituras.

Como el MTD de RAM puede desplazar los índices (`mtd0` deja de ser `uboot`),
el init localiza la partición `ubi` por nombre en `/proc/mtd` antes de hacer
`ubiattach`. En el arranque TFTP la NAND se lee; cuando el `.y3` está
instalado, `rootfs_0` se monta en rw para `/nand` (ver abajo).

## Particiones

| MTD | Nombre | Tamaño | Uso |
|---|---|---|---|
| `mtd0` | `RouterBoot` | 16 MiB | mtdram volátil; hard config sintético |
| `mtd1` | `uboot` | 1 MiB | U-Boot; solo lectura |
| `mtd2` | `ubi` | 127 MiB | UBI con el firmware/rootfs |

### Volúmenes UBI del ED500

El firmware stock crea estos volúmenes (`format_system_2` del entorno de
U-Boot). Los tamaños son los de fábrica; `ubiupdatevol --size` puede
reducirlos al instalar una imagen más pequeña.

| Volumen | Tamaño | Uso |
|---|---:|---|
| `env1` | `0x1f000` (126.976 B) | entorno de U-Boot, copia 1 |
| `env2` | `0x1f000` (126.976 B) | entorno de U-Boot, copia 2 (redundante) |
| `rootfs_0` | `0x3a20000` (60.948.480 B, 480 LEBs) | firmware/rootfs; aquí instala el `.y3` |
| `rootfs_1` | `0x3a20000` (60.948.480 B, 480 LEBs) | copia stock de recuperación manual; **no se monta ni se arranca** |
| `usr_data` | `0x22e000` (2.285.568 B) | datos de usuario del stock |

El `.y3` se instala **solo en `rootfs_0`** con `run update_image`; no se usa
la web stock ni el banco siguiente. `rootfs_1` no se monta ni se arranca: si
existe, es una copia stock para recuperación manual desde U-Boot. `root_vol`
es `rootfs_0` y `boot_cnt_primary` es el único flag de arranque que se toca;
no hay lógica A/B.

### Instalación y persistencia

- U-Boot `boot_ubi` monta `ubi0:${root_vol}` y carga `/boot/uImage` y
  `/boot/norrland.dtb`. No hay TFTP.
- El init del port monta **`rootfs_0`** en **rw** en `/nand` y enlaza
  `/flash/rw` → `/nand/rw`. La config y los logs de RouterOS persisten.
- La imagen lleva un `pad` de 30 MB que se borra en el primer arranque; deja
  espacio para `/flash/rw` sin tener que redimensionar el volumen.
- `bootok` resetea **`boot_cnt_primary`** después de comprobar que la web/API
  responde, igual que `/etc/init.d/bootcount` del stock. `boot_cnt_alt` no se
toca y `rootfs_1` no se arranca.

Detalle completo: **[FLASH-Y3.md](FLASH-Y3.md)**. Verificación offline, sin
abrir `/dev/mtd` ni `/dev/ubi`: `bash tools/verify-offline.sh`.

El init monta `rootfs_0` en **rw** en `/nand` (y lo enlaza como
`/flash/rw`). **`rootfs_1` no se monta** en el arranque normal: si existe, es
la copia stock para recuperación manual desde U-Boot. Si el bootargs no trajo
`ubi.mtd=ubi,2048,30`, el fallback es:

```sh
MTDNUM=$(sed -n 's/^\(mtd[0-9][0-9]*\):.*"ubi"$/\1/p' /proc/mtd | head -1 | sed 's/mtd//')
# Con el mtdram RouterBoot delante, ubi suele ser mtd2; mejor buscarlo.
# BusyBox exige /dev/ubi_ctrl como último argumento
ubiattach -m "$MTDNUM" -d 0 -O 2048 /dev/ubi_ctrl
# mtd-utils no lo pide
ubiattach -m "$MTDNUM" -d 0 -O 2048
```

`mtd1` es el bloque de U-Boot; no se toca. `mtdblock0` es el mtdram
`RouterBoot` (RAM) y `mtdblock2` la visión cruda de la NAND; ninguno es el
`/dev/flash` que espera RouterOS: `flash.ko` registra su propio dispositivo
de caracteres. No crees un symlink manual a `/dev/mtdblock0`.

## Comprobar la NAND desde el shell

Dentro del initramfs o del shell de RouterOS:

```sh
cat /proc/mtd
ls -l /dev/mtd* /dev/mtdblock* /dev/ubi* 2>/dev/null
ubiattach -m 1 -d 0 -O 2048
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

- **Probado (build #71, 2026-11-20):** detección del chip, BBT en las páginas
  65472/65408, attach de UBI (`VID header offset: 2048`, `data offset: 4096`)
  y montaje en ro de `rootfs_0` (volumen 2) y `rootfs_1` (volumen 3) con el
  kernel 5.6.3. El shell `~ #` de RouterOS arranca después.
- **Probado (build #72, 2026-11-20):** `sysinit` se ejecuta y `flash.ko`
  acepta el MTD RAM (`new-flash: starting...` → `using MTD device`). Pero el
  siguiente paso fallaba: la flash estaba en blanco y no tenía el *hard
  config* de RouterBoot.
- **Probado (build #76, 2026-11-20):** el init escribe hard y soft config
  sintéticos en el mtdram antes de `sysinit` (product ID 000, MAC real del
  ED500, serial `W.3620220010`). La consola muestra `magics: hard=64726148
  soft=74666f53`; `flash.ko` ya no imprime `could not get flash soft info`,
  carga y registra `/dev/flash`. `mount none /flash` sigue en `EINVAL` porque
  `diskd` pasa `fstype=NULL` al `mount`; no es un fallo de `flash.ko`. No se
  toca la NAND ni la licencia.
- **Construido, no flasheado (2026-11-21):** `out/ED500-routeros-7.17-nand.y3`
  (53.613.270 B, MD5 `3e9b37d712ad6610bbaa2dc7d7ae2ccb`) lleva una UBIFS de
  422 LEBs con `/boot/uImage`, `/boot/norrland.dtb`, `/rw` y el `pad`. La
  escritura real en NAND, el arranque de `iboot` y la persistencia tras un
  reinicio **no se han probado**. Ver [FLASH-Y3.md](FLASH-Y3.md).
- **No probado como escritura:** el repo no ejecuta `ubi write` ni
  `flash_erase` en el arranque TFTP. La instalación es un paso explícito por
  `run update_image` desde U-Boot, que escribe `rootfs_0`; la web stock no se
  usa y no hay fallback A/B.
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

El `.y3` ya está construido y verificado a nivel de contenedor:
`out/ED500-routeros-7.17-nand.y3` (422 LEBs, 53.613.270 B). La instalación
en NAND es el paso siguiente; el arranque TFTP a RAM sigue siendo el método
de prueba que no escribe flash. Procedimiento: **[FLASH-Y3.md](FLASH-Y3.md)**.
