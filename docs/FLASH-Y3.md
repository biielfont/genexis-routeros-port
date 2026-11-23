# Instalar en NAND con un `.y3`

> **Estado (2026-11-21).** El `.y3` está **construido y verificado** a nivel de
> contenedor, UBIFS y contenido. **No se ha flasheado**: la placa quedó haltada
> y la prueba en hardware es el lunes. El arranque TFTP a RAM sigue disponible
> como recuperación y no escribe NAND. No ejecutes la instalación sin backup y
> sin tener claro cómo volver al firmware stock.

## El contenedor

Un `.y3` del ED500 es **cabecera de texto de 1024 bytes + rootfs UBIFS +
pkginfo + MD5**. La cabecera real del firmware oficial `GNX-4.3.6.170-R`:

```text
IntenoIopY
version 5
integrity MD5SUM
git 71b8d1b
board NORRLAND
chip grx550
arch all mips_24kc_nomips16
model NORRLAND
release GNX-4.3.6.170-R
customer GNX
ubifsofs 1024
ubifs 44949504
pkginfoofs 44950528
pkginfo 28342
scrofs 44978870
scr 0
sigofs 44978870
sig 0          <-- no hay firma criptografica
md5ofs 44978870
md5 32
size 44978902
```

Dos hechos comprobados, no supuestos:

- `sig 0`: el update **no verifica una firma**, solo el MD5 en ASCII.
- Reconstruir el firmware oficial con `08-y3tool.py` da un fichero **idéntico
  byte a byte** al de Genexis. El contenedor está entendido.

Herramienta:

```bash
python3 08-y3tool.py info   out/ED500-stock-original.y3
python3 08-y3tool.py unpack out/ED500-stock-original.y3 /tmp/ext
python3 08-y3tool.py build  nuevo.y3 --ubifs rootfs.ubifs --pkginfo pk.txt \
        --release GNX-4.3.6.999-R
```

## El `.y3` de este port

| Campo | Valor |
|---|---|
| Fichero | `out/ED500-routeros-7.17-nand.y3` |
| Tamaño | 53.613.270 B |
| MD5 | `3e9b37d712ad6610bbaa2dc7d7ae2ccb` |
| UBIFS | 53.583.872 B, **422 LEBs** (máximo 480) |
| Kernel | `out/uImage-563`, 21.899.532 B, MD5 `e2e8698843a1278da58e5d9178c89f5a` |
| DTB | `norrland.dtb` de la placa (13.711 B) |
| Firma | 0 (solo MD5, como el oficial) |

La UBIFS está pensada para **`rootfs_0`** (`0x3a20000` = 480 LEBs de 126.976 B);
`run update_image` escribe ahí. La web stock no se usa: el sistema activo es
solo `rootfs_0`. Lleva:

```text
/boot/uImage        kernel 5.6.3 con el initramfs de RouterOS
/boot/norrland.dtb  DTB del ED500 (SSO/LEDs/boton reset)
/boot/VERSION       identificacion
/etc/os-release     identificacion
/rw/                configuracion persistente de RouterOS
/pad                30 MB aleatorios (se borran en el primer arranque)
```

`/pad` parece un desperdicio, pero es deliberate: `yimage`/`ubiupdatevol`
ajustan el volumen al tamaño de la imagen. Sin el pad, `rootfs_0` quedaría en
~22 MB y no habría sitio para la config de RouterOS. Al borrarlo en el primer
arranque quedan **~30 MB libres** para `/flash/rw`. La imagen sigue cabiendo en
los 60.948.480 B del volumen.

## Cómo se construye

Requisitos: `mkfs.ubifs` (mtd-utils), Python 3 y, para reutilizar el `pkginfo`
del firmware stock, `out/ED500-stock-original.y3`. El kernel y el DTB salen de
`build-563.sh`.

```bash
sudo bash build-563.sh
bash tools/make-y3.sh
```

`make-y3.sh` hace:

1. copia `out/uImage-563` y el DTB de la placa a `out/y3-rootfs/boot/`;
2. crea `/rw` y el `pad` aleatorio de 30 MB;
3. genera la UBIFS con la geometría de la NAND:
   `mkfs.ubifs -m 2048 -e 126976 -c 480 -x zlib`;
4. comprueba que la imagen no pasa de 480 LEBs ni de `0x3a20000` bytes;
5. reutiliza el `pkginfo` del `.y3` stock (o genera uno mínimo);
6. empaqueta con `08-y3tool.py` y verifica tamaño, MD5, magia UBIFS y que
   `/boot/uImage` y `/boot/norrland.dtb` coinciden byte a byte con los de
   entrada.

Salida esperada:

```text
make-y3: out/ED500-routeros-7.17-nand.y3
  UBIFS 53583872 B, 422 LEBs (max 480), pad 30 MB
  MD5 3e9b37d712ad6610bbaa2dc7d7ae2ccb
```

## Cómo se instala

### A. Desde U-Boot (única vía; un solo banco)

Copia el `.y3` a la raíz de tu servidor TFTP con el nombre **`last.y3`**. En el
prompt `IOPSYS 2 grx500 #`:

```text
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.161
run update_image
setenv root_vol rootfs_0
setenv boot_cnt_primary 0
setenv boot_cnt_alt 0
saveenv
reset
```

`update_image` está definido en el U-Boot de Genexis como:

```text
update_image=if ${dl_prog} ${loadaddr} last.y3; then yimage burn rootfs_0;setenv root_vol rootfs_0;fi;
```

Es decir: descarga `last.y3` a `0x80800000` y escribe la UBIFS en **`rootfs_0`**.
Los `setenv`/`saveenv` posteriores dejan `rootfs_0` como único volumen activo
y los contadores a cero. No se usa la web stock ni el banco siguiente.

> **No uses `update_nandboot` ni `update_uboot`.** Solo se instala el rootfs;
> el U-Boot de Genexis se queda como está. **No hay arranque A/B**: `rootfs_1`
> no se monta ni se usa; si existe, es solo una copia stock para recuperación
> manual.

### B. Recuperación al firmware stock

Guarda `out/ED500-stock-original.y3` (44.978.902 B, MD5
`45421c58132c78fa932fa23ef26e001a`) en el TFTP como `last.y3` y ejecuta el
mismo `run update_image`: escribe el stock en `rootfs_0`, fija `root_vol` y al
reiniciar vuelve Genexis. Es la vuelta limpia, con un solo sistema activo.

> **No uses `update_nandboot` ni `update_uboot`.** Solo se escribe el rootfs;
> el U-Boot de Genexis se queda como está.

## Qué pasa en el arranque desde NAND

El entorno stock arranca con:

```text
bootcmd=rescue;iboot
boot_ubi=run bootargs_ubi;ubifsmount ubi0:${root_vol};
         ubifsload ${loadaddr} /boot/uImage;
         if ubifsload ${fdtaddr} /boot/${fdtfile}; then bootm ${loadaddr} - ${fdtaddr}; fi
```

Es decir: **no hay TFTP**. U-Boot monta el volumen UBI, carga `/boot/uImage` y
`/boot/norrland.dtb` y ejecuta `bootm`. El kernel lleva su initramfs dentro; el
`init` del port:

1. adjunta UBI con el offset correcto (`-O 2048`), aunque el bootargs de NAND
   diga `ubi.mtd=ubi,0,30`;
2. monta **`rootfs_0`** (el único volumen activo) en **rw** en `/nand`;
3. hace `/flash/rw` → `/nand/rw`, así que la config, los logs y el estado de
   RouterOS **sobreviven al reinicio**;
4. borra `/pad` para liberar los ~30 MB;
5. arranca `sysinit`; un ayudante `bootok` espera a que la web/API responda y
   resetea **`boot_cnt_primary`** con `fw_setenv`, igual que
   `/etc/init.d/bootcount` del firmware stock. Sin ese reset, `iboot` acabaría
   intentando el banco de recuperación tras varios reinicios.

El kernel lleva `clk_ignore_unused` activado por defecto (el bootargs de NAND
no lo trae) y el init fija `panic=20` para que un pánico reinicie y U-Boot
pueda volver al otro banco.

## Verificación realizada

- `08-y3tool.py info`: `size` real = declarado; MD5 coincide; `sig 0`; magia
  UBIFS `31181006`.
- UBIFS: `leb_cnt 423`, `max_leb_cnt 480`, `min_io_size 2048`, `leb_size
  126976`; 53.710.848 B < 60.948.480 B del volumen.
- Extracción con `ubireader_extract_files`: `/boot/uImage`,
  `/boot/norrland.dtb`, `/boot/VERSION`, `/etc/os-release`, `/rw` y `/pad`
  presentes.
- `/boot/uImage` dentro del `.y3` es **byte a byte** `out/uImage-563`
  (MD5 `66497d47…`); el DTB coincide con el del árbol del kernel.
- Initramfs: `fw_printenv` y `fw_setenv` estáticos presentes; init con
  el volumen activo rw, `/flash/rw`, `bootok`, `clk_ignore_unused` y `tcp/tcp6`.

### Verificación offline reproducible

```bash
bash tools/verify-offline.sh   # WSL/Linux; no abre /dev/mtd ni /dev/ubi
```

El script comprueba, sobre ficheros y artefactos:

- tamaño, MD5, firma y geometría del `.y3`; `/boot/uImage`/DTB byte a byte;
  `/rw` y `/pad`;
- que el initramfs lleva `busybox`, `devlog`, `fw_printenv`/`fw_setenv` y que
  el init copia los dos primeros al rootfs antes de los `chroot` (si no, el
  `netup`/`bootok` fallarían en silencio) y monta el volumen activo;
- que `sysinit` busca las cuatro rutas de autorun que escribe el init
  (`/flash/autorun.scr`, `/rw/autorun.scr`, `/rw/store/autorun.scr` y
  `/pckg/branding/rw/autorun.scr`);
- un entorno U-Boot real en fichero, con las dos copias redundantes: lectura,
  escritura, CRC y caída de la primera a la segunda;
- el `bootok` con `rootfs_0`, con `rootfs_1` (que debe ignorar), con el
  servicio caído y con el entorno ilegible, incluida la limpieza del autorun;
- que `run update_image` escribe `rootfs_0` y fija `root_vol=rootfs_0`, y que
  el stock `.y3` sirve para devolver el firmware Genexis.

**No verificado:** la escritura real en NAND, el arranque de `iboot` con esta
imagen, la persistencia tras un reinicio, el reset/LEDs y el primer login. Eso
es la prueba del lunes.

## Backup y recuperación

Antes de escribir:

1. **El stock se conserva en `rootfs_1`.** `rootfs_0` es el único volumen
   activo; `rootfs_1` no se monta ni se arranca. Si el port no arranca, la
   vuelta es manual desde U-Boot con `out/ED500-stock-original.y3` (o con
   `run update_image`), no un fallback automático.
2. **Backup completo (recomendado).** Desde U-Boot, leer la UBI y enviarla al
   PC por TFTP:

   ```text
   nand read 0x81000000 0x100000 0x7f00000
   tftpput 0x81000000 0x7f00000 backup-ubi.bin
   ```

   `0x100000` es el inicio de la partición `ubi`; `0x7f00000` son los 127 MiB.
   Necesitas un servidor TFTP que acepte escrituras (`tftpput`), no el servidor
   de solo lectura de `catch_final.py`.

3. **Volver al stock.** Con `out/ED500-stock-original.y3` como `last.y3` y
   `run update_image` se recupera el firmware Genexis en `rootfs_0`. Es la
   vuelta recomendada; no depende de `rootfs_1` ni de un arranque A/B.

No escribas NAND sin entender el mapa de volúmenes
([NAND-UBI.md](NAND-UBI.md)) y sin tener el cable serie disponible.

## Histórico

El formato se descifró en noviembre de 2026 a partir del firmware oficial y de
la herramienta `08-y3tool.py`. Los intentos anteriores (`ED500-nuestro-kernel.y3`,
`ED500-net618.y3`) sirvieron para validar el contenedor, pero no llevaban el
initramfs de RouterOS ni la persistencia de `/flash/rw`. El artefacto actual es
`ED500-routeros-7.17-nand.y3`.
