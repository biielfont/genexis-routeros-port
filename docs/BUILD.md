# Compilar el kernel y el `uImage`

Esta guía describe el camino **actual** (`build-563.sh`). Los scripts `01…04`
son el bootstrap que deja el árbol `/opt/ros-port/linux-5.6.3` y el initramfs
listos; `05`/`06` y los `patch_*`/`check_*` son históricos.

## Entorno soportado

- Linux x86_64 o WSL2. Los scripts escriben en `/opt/ros-port` y `/opt/toolchain`.
- Usuario con permisos de escritura en `/opt` (o ejecutar con `sudo`).
- Python 3.8+ para los parches y utilidades.
- `git` no es necesario para compilar, pero sí para clonar el repo.
- No se necesita QEMU para el camino TFTP del ED500.

### Paquetes del sistema

En Debian/Ubuntu/Kali:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  make bc flex bison libssl-dev libelf-dev xz-utils patch wget \
  ca-certificates u-boot-tools squashfs-tools cpio gzip bzip2 python3-pip
```

`u-boot-tools` aporta `mkimage`; `squashfs-tools` aporta `unsquashfs`/`mksquashfs`.

## 1. Bootstrap del árbol 5.6.3

Desde la raíz del repo:

```bash
sudo bash 01-build-gpl-kernel.sh
sudo bash 02-apply-platform.sh
sudo bash 03-build-intel-mips.sh     # primera compilación de control
sudo bash 04-build-initramfs.sh      # busybox + initramfs base
```

Qué hace cada uno:

| Script | Efecto |
|---|---|
| `01-build-gpl-kernel.sh` | Descarga la toolchain Bootlin, Linux 5.6.3, el parche GPL de MikroTik y `mips.config`; aplica el parche y compila un `vmlinux` de control |
| `02-apply-platform.sh` | Copia `tree/arch/mips/intel-mips` y `mach-intel-mips`, engancha `INTEL_MIPS` en Kconfig/Kbuild y deja una config mínima |
| `03-build-intel-mips.sh` | Compila la plataforma mínima y deja el log en `/opt/ros-port/build4.log` |
| `04-build-initramfs.sh` | Compila BusyBox estático MIPS BE, crea `/opt/ros-port/initramfs` y deja un init de rescate |

Rutas que espera el build actual:

```text
/opt/toolchain/bin/mips-buildroot-linux-gnu-*
/opt/ros-port/linux-5.6.3/
/opt/ros-port/initramfs/
/opt/ros-port/fw/lantiq/xrx500-phy-fw.bin
```

El árbol de kernel **no se versiona** en este repo: son cientos de MiB y tienen
su propia licencia. El parche y el `mips.config` se descargan de las fuentes
GPL de MikroTik; el espejo que usa `01` es
[`tikoci/mikrotik-gpl`](https://github.com/tikoci/mikrotik-gpl).

## 2. Rootfs de RouterOS

El rootfs no se redistribuye. Descarga el `.npk` oficial de **RouterOS 7.17
mipsbe** desde MikroTik y extrae `rootfs.squashfs`. Según la herramienta que
uses, el contenedor se abre con `7z`, `binwalk` o utilidades de RouterOS; el
objetivo es localizar el squashfs y dejarlo aquí:

```text
ros/rootfs.squashfs
```

El `.gitignore` excluye `ros/*.npk`, `ros/*.squashfs` y `ros/rootfs/`. No subas
ese contenido al repositorio.

## 3. Build actual

```bash
sudo bash build-563.sh
```

El script, en este orden:

1. ejecuta `parche_arranque.py` sobre `/opt/ros-port/linux-5.6.3` (idempotente);
2. copia `init-initramfs.sh` al initramfs y `ros/rootfs.squashfs` como
   `ros.squashfs`;
3. compila `phyreg` y `swstats` estáticos;
4. activa las opciones de kernel necesarias (UBI/UBIFS, NAND xrx500, DSA/GSWIP,
   PHYLINK, netfilter, futex, squashfs, loop, etc.);
5. compila `vmlinux`, comprueba el DTB y empaqueta `out/uImage-563` para
   `0x80500000`.

Si falla, el script no deja un `uImage` viejo: sale con error. Los logs están en
`/opt/olddef.log` y `/opt/build563.log`.

### Verificación mínima

```bash
ls -l out/uImage-563
md5sum out/uImage-563
/opt/toolchain/bin/mips-buildroot-linux-gnu-readelf -h \
  /opt/ros-port/linux-5.6.3/vmlinux | grep -E 'Data|Entry'
```

Invariantes que comprueba el propio script:

- DTB con `nand-ecc-strength = <4>`;
- DTB con `nand-on-flash-bbt`;
- bootargs con `ubi.mtd=ubi,2048,30` (VID header de la UBI stock);
- `mtdram` activo y renombrado a `RouterBoot` (shim de `/flash`);
- initramfs con el rootfs de RouterOS y `rb_hardconfig.bin` (identidad
  RouterBoot sintética: hard config y bloque `Soft`);
- `entry` y `load` en `0x80500000`;
- endianness **big-endian** (el userland de RouterOS es mipsbe).

El `uImage-563` de referencia de esta investigación (build #76) mide
**19.681.356 bytes** y tiene md5 **`eba17e8836b4ee2e3ec35829a56538d0`**. El
tamaño cambia si tocas initramfs, rootfs o configuración; no es un valor fijo
del build.

## 4. Notas de reproducibilidad

- `build-563.sh` usa `AQUI=$(cd "$(dirname "$0")" && pwd)`, así que funciona
  desde cualquier directorio mientras se invoque con su ruta.
- `02`, `04`, `05` y `06` ya calculan su propia ruta; no dependen de
  `C:\Users\BFR\...`. `01` y el árbol del kernel siguen usando `/opt/ros-port`
  a propósito.
- El build no es hermético: descarga toolchain y fuentes, y usa el rootfs que
  pongas en `ros/`. Para reproducibilidad exacta, anota la versión del `.npk`,
  del parche GPL y de la toolchain que uses.
- El build #76 está probado en placa (2026-11-20); si cambias el kernel,
  vuelve a probar en placa antes de dar por bueno el `uImage`.

Siguiente paso: **[BOOT-TFTP.md](BOOT-TFTP.md)**.
