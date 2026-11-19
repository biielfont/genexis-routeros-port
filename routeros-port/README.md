# Genexis Pure ED500 · port de RouterOS 7.17 (mipsbe)

Port de investigación de **RouterOS 7.17 mipsbe** al router **Genexis Pure ED500**
(Intel/Lantiq **GRX350**, MIPS BE interAptiv de dos núcleos), arrancando por
**TFTP a RAM** sin escribir la flash.

[Estado y progreso](docs/PROGRESS.md) ·
[Mapa visual](progress.svg) ·
[Documentación](docs/README.md) ·
[Cómo contribuir](CONTRIBUTING.md) ·
[Aviso legal](NOTICE.md)

> **Proyecto independiente.** No está afiliado a MikroTik, Genexis ni Intel/Lantiq.
> Este repositorio **no contiene ni redistribuye software de MikroTik**. El `.npk`
> de RouterOS y su rootfs se obtienen de MikroTik bajo sus propias condiciones.
> No hay ningún método para saltarse la licencia: si quieres usar RouterOS,
> necesitas una licencia válida.

---

## Qué es esto

El ED500 lleva un SoC GRX350 con dos núcleos MIPS interAptiv, NAND SLC de
128 MiB, switch GSWIP y PHYs XWAY. RouterOS 7.17 para `mipsbe` corre sobre Linux
**5.6.3**, el mismo kernel que MikroTik publica en sus fuentes GPL. La idea del
port es reutilizar ese kernel, parchear lo que falta del SoC y arrancar el
rootfs oficial de RouterOS en RAM, sin tocar la NAND.

El repo contiene las herramientas, parches y documentación del proceso. **No es
un firmware alternativo completo**: es un entorno de investigación reproducible.

## Estado, en corto

![Mapa de progreso](progress.svg)

**60% del port completado (60/100 puntos de peso).** El treemap muestra en verde
lo verificado y en gris lo pendiente; el detalle y la evidencia están en
**[docs/PROGRESS.md](docs/PROGRESS.md)**.

- **Funciona en hardware:** kernel 5.6.3, consola `ttyLTQ0`, Ethernet DSA/GSWIP
  a 1 Gbps, NAND con BCH-4/BBT, UBI/UBIFS en lectura, rootfs de RouterOS con
  overlay y shell `~ #`.
- **No funciona todavía:** la red dentro de RouterOS (faltan el *fastpath*
  binario y un driver de switch de MikroTik), la licencia demo (no hay disco
  MikroTik) y la instalación persistente en NAND.
- **Artefacto actual:** `out/uImage-563` se compila con `build-563.sh`; la
  última prueba de hardware registrada corresponde a builds anteriores
  (#29/#62) y llega a shell. El artefacto final está pendiente de una nueva
  prueba en placa.

El **mapa visual** está en `progress.svg`; el detalle completo, con la tabla de
hitos, evidencia, bloqueos y siguientes pasos, está en
**[docs/PROGRESS.md](docs/PROGRESS.md)**. El mapa es un treemap de dos paneles
(plataforma y RouterOS), con una celda por punto de peso.

### Los dos muros

1. **Red de RouterOS.** Sus módulos `packet_hook.ko`, `switch.ko`, `bridge2.ko`
   y `phy_helper.ko` piden símbolos que no existen en las fuentes GPL ni en
   ningún `.ko` del paquete (`netif_receive_try_fp`, `fast_path_start_xmit`,
   `register_fast_path`, `skb_bin_*`, `phy_setup`, `custom_packet_hook_rx`…).
   Son del *fastpath* binario de MikroTik. Además, `switch.ko` es el driver de
   *sus* switches, no del GSWIP del GRX350.
2. **Licencia.** RouterOS deriva su *software ID* del disco (`/dev/mtdblock0`) y
   aquí la NAND contiene el firmware Adamo, no un disco MikroTik. El chequeo
   acaba en `Demo license expired!`. Una licencia CHR (x86) no sirve para un
   equipo MIPS BE. Este repo no intenta evitar ese control.

---

## Quick start

### 1. Requisitos

- Linux o WSL2 con permisos para escribir en `/opt` (los scripts usan `/opt/ros-port`).
- Toolchain MIPS de Bootlin `mips32--glibc--stable-2024.05-1`.
- Fuentes Linux 5.6.3 + parche y `mips.config` de MikroTik GPL.
- `make`, `bc`, `flex`, `bison`, `libssl-dev`, `libelf-dev`, `xz-utils`,
  `patch`, `wget`, `mkimage` (`u-boot-tools`), `squashfs-tools`, `cpio`, `gzip`,
  `bzip2` y Python 3.
- Un `.npk` oficial de RouterOS **7.17 mipsbe** para extraer
  `ros/rootfs.squashfs` (no se versiona).
- Para la consola: COM4 a 115200 8N1 (o define `ED500_PORT`) y una LAN del ED500.

### 2. Preparar el árbol

```bash
git clone <tu-fork> routeros-port
cd routeros-port
python3 -m pip install -r requirements.txt
```

Copia el rootfs extraído del `.npk` a `ros/rootfs.squashfs`. El `.gitignore`
excluye `ros/`, `out/` y `logs/`: no los subas.

El bootstrap completo (toolchain, fuentes GPL, plataforma, busybox/initramfs y
rootfs) está en **[docs/BUILD.md](docs/BUILD.md)**. El camino corto, si el árbol
`/opt/ros-port/linux-5.6.3` ya está preparado, es:

```bash
sudo bash build-563.sh
```

Salida esperada: `out/uImage-563` (unos 19,7 MB), con carga y entrada en
`0x80500000`. El script comprueba DTB BCH-4, `nand-on-flash-bbt`, `ubi.mtd=ubi`
y que el initramfs tenga el rootfs de RouterOS.

### 3. Arrancar por TFTP (RAM)

```bash
python catch_final.py --horas 6
# o en Windows: doble clic en ARRANCAR-563.bat
```

El cazador sirve `out/uImage-563` por TFTP, espera el prompt `grx500 #` de
U-Boot, ejecuta `tftpboot` y `bootm`, y comprueba el tamaño transferido. **Todo
va a RAM**: la NAND no se escribe y el firmware original sigue arrancando si no
hay cazador.

Detalle, comandos manuales y solución de problemas:
**[docs/BOOT-TFTP.md](docs/BOOT-TFTP.md)**.

### 4. Reinicio remoto

```bash
python uboot_cycle.py status
python uboot_cycle.py cycle
python uboot_cycle.py watch --horas 6
```

`uboot_cycle.py` reinicia por software (U-Boot `reset` o RCU `0x16000010`, bit
30) y vuelve a cargar la imagen, sin cortar la corriente. No toca la NAND.
Ver **[docs/BOOT-TFTP.md](docs/BOOT-TFTP.md#reinicio-remoto)**.

---

## Estructura

| Ruta | Qué es |
|---|---|
| `build-563.sh` | **Build actual**: parchea, compila 5.6.3 y empaqueta `out/uImage-563` |
| `parche_arranque.py` | Todos los parches del árbol, idempotentes |
| `init-initramfs.sh` | Init: overlay, red, NAND/UBI y arranque de RouterOS |
| `phyreg.c`, `swstats.c` | Diagnóstico de PHY (MDIO) y contadores del switch |
| `catch_final.py` + `tftplib.py` | Cazador de U-Boot y servidor TFTP integrado |
| `uboot_cycle.py` | Reset, catch, TFTP y `bootm` por consola serie |
| `ARRANCAR-563.bat` | Lanzador de Windows para `catch_final.py` |
| `01…04-*.sh` | Bootstrap del árbol 5.6.3, plataforma y initramfs |
| `docs/` | Guías actuales, referencia e histórico |
| `tools/progress.py`, `progress.json`, `progress.svg` | Generador, datos y mapa visual |
| `refs/`, `tree/` | DTS y parches de plataforma de referencia |
| `ros/` | **No versionado**: `.npk` y `rootfs.squashfs` |
| `out/`, `logs/` | **No versionados**: artefactos y registros de consola |
| `check_*.sh`, `patch_*.py`, `boot*.py` | Scripts históricos de investigación; ver `docs/history/` |

## Documentación

- **[Estado y progreso](docs/PROGRESS.md)** — treemap, tabla de hitos, evidencia y bloqueos.
- **[Compilación](docs/BUILD.md)** — bootstrap, dependencias y verificación.
- **[Arranque por TFTP](docs/BOOT-TFTP.md)** — cazador, comandos U-Boot y reset remoto.
- **[NAND y UBI](docs/NAND-UBI.md)** — geometría, BCH-4/BBT, montaje en lectura.
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** — fallos típicos y qué mirar.
- **[Y3 / flasheo experimental](docs/FLASH-Y3.md)** — histórico, no es el método actual.
- **[Índice de docs](docs/README.md)**.

## Alcance legal y seguridad

- No se incluye ni se redistribuye RouterOS, el `.npk`, el rootfs ni volcados de
  NAND. No se incluye ningún *keygen*, parche de licencia o bypass.
- El arranque por defecto es **RAM/TFTP**. No escribas NAND sin un backup
  verificado y sin entender el mapa de particiones.
- Los logs pueden contener IPs, MACs o rutas de tu red. Revísalos antes de
  adjuntarlos a un issue.
- Las fuentes del kernel y los parches de MikroTik tienen su propia licencia;
  consulta `NOTICE.md`.

## Contribuir

Se aceptan mejoras de documentación, reproducción, diagnóstico y drivers
propios. Antes de abrir un PR lee **[CONTRIBUTING.md](CONTRIBUTING.md)**. No
adjuntes software propietario ni resultados de licencia modificados.
