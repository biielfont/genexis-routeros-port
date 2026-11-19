# Genexis Pure ED500 — port nativo de RouterOS 7.17

Port de investigación de **RouterOS 7.17 mipsbe** al router **Genexis Pure
ED500** (Intel/Lantiq **GRX350**, MIPS big-endian interAptiv), arrancando por
**TFTP a RAM** sin escribir la flash.

[Estado y progreso](PROGRESS.md) · [Documentación](routeros-port/docs/README.md) ·
[Mapa visual](routeros-port/progress.svg) · [Contribuir](routeros-port/CONTRIBUTING.md)

> **Proyecto independiente y sin software de MikroTik.** No está afiliado a
> MikroTik, Genexis ni Intel/Lantiq. El `.npk` de RouterOS, su rootfs y sus
> binarios se obtienen aparte, bajo las condiciones de MikroTik. Este
> repositorio no los redistribuye y no contiene ningún *keygen*, parche de
> licencia o bypass del *software ID*.

---

## Estado actual

![Mapa de progreso](routeros-port/progress.svg)

**60% del port completado (60/100 puntos de peso).** El mapa es un SVG
generado desde datos versionados; se embebe aquí y en
[`PROGRESS.md`](PROGRESS.md). No hay una página HTML duplicando el texto: el
detalle vive en Markdown.

| Área | Peso | Hecho | % | Estado |
|---|---:|---:|---:|---|
| Arranque y plataforma | 20 | 20 | 100% | verificado |
| Ethernet / switch / PHY en Linux | 10 | 10 | 100% | verificado |
| NAND / UBI / UBIFS en lectura | 10 | 10 | 100% | verificado |
| Rootfs / overlay / shell de RouterOS | 10 | 10 | 100% | verificado |
| Módulos de RouterOS | 10 | 3 | 30% | parcial |
| Red dentro de RouterOS | 20 | 1 | 5% | bloqueado |
| Licencia RouterOS | 10 | 0 | 0% | bloqueado |
| Instalación persistente / `.y3` | 5 | 1 | 20% | parcial |
| Herramientas remotas y documentación | 5 | 5 | 100% | verificado |
| **Total** | **100** | **60** | **60%** | |

El desglose completo, la evidencia, los bloqueos y el historial están en
**[PROGRESS.md](PROGRESS.md)**.

### Funciona hoy en hardware

- Kernel Linux **5.6.3** de MikroTik compilado para el GRX350.
- Arranque por **TFTP a RAM** y consola `ttyLTQ0` a 115200.
- **Ethernet a 1 Gbps**: DSA, switch GSWIP XRX500 y PHY XWAY.
- **NAND de 128 MiB** (Macronix MX30LF1G18AC) con ECC **BCH-4** y BBT.
- **UBI/UBIFS en lectura**: `rootfs_0` y `rootfs_1` montados en solo lectura.
- **Rootfs oficial de RouterOS**: Squashfs, overlay en tmpfs y shell `~ #`.
- `flash.ko` de RouterOS cargado.

### No funciona todavía

- **Red dentro de RouterOS.** Sus módulos `packet_hook.ko`, `switch.ko`,
  `bridge2.ko` y `phy_helper.ko` dependen de símbolos del *fastpath* binario de
  MikroTik (`netif_receive_try_fp`, `fast_path_start_xmit`,
  `register_fast_path`, `skb_bin_*`, `phy_setup`, `custom_packet_hook_rx`…).
  Tampoco existe un driver de RouterOS para el GSWIP del GRX350.
- **Licencia RouterOS.** RouterOS deriva su *software ID* de un disco
  MikroTik; aquí la NAND contiene el firmware Adamo y el chequeo termina en
  `Demo license expired!`. Una licencia CHR (x86) no sirve para MIPS BE.
- **Instalación persistente.** El formato `.y3` está investigado, pero no se
  ha escrito NAND ni se ha probado una recuperación. El método actual es
  TFTP a RAM.
- **Artefacto final.** `out/uImage-563` se compiló y empaquetó, pero la última
  prueba en placa registrada corresponde a builds anteriores (#29/#62). Hay que
  repetirla antes de presentarlo como probado.

---

## Qué es este proyecto

El ED500 usa un SoC GRX350 de dos núcleos MIPS interAptiv, NAND SLC de 128 MiB,
switch GSWIP y PHYs XWAY. RouterOS 7.17 para `mipsbe` corre sobre Linux 5.6.3,
el mismo kernel que MikroTik publica en sus fuentes GPL. La idea del port es
reutilizar ese kernel, portar lo que falta del SoC y arrancar el rootfs oficial
de RouterOS en RAM, sin tocar la NAND.

El repositorio contiene las herramientas, parches, diagnósticos y documentación
del proceso. **No es un firmware alternativo completo**: es un entorno de
investigación reproducible. La red del kernel Linux funciona; la red de
RouterOS y la licencia son dos límites distintos.

### El hardware

| Pieza | Detalle |
|---|---|
| SoC | Intel/Lantiq GRX350, MIPS BE interAptiv de dos núcleos |
| Kernel de RouterOS | Linux 5.6.3 (`mipsbe`) |
| NAND | Macronix MX30LF1G18AC, 128 MiB SLC |
| ECC / BBT | BCH-4, `nand-on-flash-bbt`; BBT 65472/65408 páginas |
| Switch | GSWIP XRX500 vía DSA (`gswip3`) |
| PHY | XWAY; enlace verificado a 1 Gbps |
| Consola | `ttyLTQ0`, 115200 8N1 |
| Arranque actual | TFTP a RAM; la NAND no se escribe |

---

## Quick start

### Requisitos

- Linux o WSL2 con permisos para escribir en `/opt` (los scripts usan
  `/opt/ros-port`).
- Toolchain MIPS de Bootlin `mips32--glibc--stable-2024.05-1`.
- Fuentes Linux 5.6.3 + parche y `mips.config` de MikroTik GPL.
- `make`, `bc`, `flex`, `bison`, `libssl-dev`, `libelf-dev`, `xz-utils`,
  `patch`, `wget`, `mkimage` (`u-boot-tools`), `squashfs-tools`, `cpio`, `gzip`,
  `bzip2` y Python 3.
- Un `.npk` oficial de RouterOS **7.17 mipsbe** para extraer
  `ros/rootfs.squashfs` (no se versiona).
- Para la consola: COM4 a 115200 8N1 (o define `ED500_PORT`) y una LAN del
  ED500.

### Preparar el árbol

```bash
git clone https://github.com/biielfont/genexis-routeros-port.git
cd genexis-routeros-port/routeros-port
python3 -m pip install -r requirements.txt
```

Copia el rootfs extraído del `.npk` a `ros/rootfs.squashfs`. El `.gitignore`
excluye `ros/`, `out/` y `logs/`: no los subas.

El bootstrap completo (toolchain, fuentes GPL, plataforma, busybox/initramfs y
rootfs) está en **[docs/BUILD.md](routeros-port/docs/BUILD.md)**. El camino
corto, si el árbol `/opt/ros-port/linux-5.6.3` ya está preparado:

```bash
sudo bash build-563.sh
```

Salida esperada: `out/uImage-563` (unos 19,7 MB), con carga y entrada en
`0x80500000`. El script comprueba DTB BCH-4, `nand-on-flash-bbt`, `ubi.mtd=ubi`
y que el initramfs tenga el rootfs de RouterOS.

### Arrancar por TFTP (RAM)

```bash
python catch_final.py --horas 6
# o en Windows: doble clic en ARRANCAR-563.bat
```

El cazador sirve `out/uImage-563` por TFTP, espera el prompt `grx500 #` de
U-Boot, ejecuta `tftpboot` y `bootm`, y comprueba el tamaño transferido. **Todo
va a RAM**: la NAND no se escribe y el firmware original sigue arrancando si no
hay cazador.

Detalle, comandos manuales y solución de problemas:
**[docs/BOOT-TFTP.md](routeros-port/docs/BOOT-TFTP.md)**.

### Reinicio remoto

```bash
python uboot_cycle.py status
python uboot_cycle.py cycle
python uboot_cycle.py watch --horas 6
```

`uboot_cycle.py` reinicia por software (U-Boot `reset` o RCU `0x16000010`, bit
30) y vuelve a cargar la imagen, sin cortar la corriente. No toca la NAND.
Ver **[docs/BOOT-TFTP.md](routeros-port/docs/BOOT-TFTP.md#reinicio-remoto)**.

---

## Estructura del repositorio

```text
README.md                  # esta portada
PROGRESS.md                # informe detallado + gráfico embebido
routeros-port/             # el port: código, parches, documentación
  progress.svg             # gráfico generado; único elemento visual
  progress.json            # datos de los hitos
  tools/progress.py        # generador del SVG, sin dependencias
  README.md                # guía técnica del port
  build-563.sh             # build completo
  parche_arranque.py       # parches idempotentes del kernel
  init-initramfs.sh        # init, overlay, red, NAND/UBI y RouterOS
  catch_final.py           # cazador U-Boot + TFTP
  uboot_cycle.py           # reset/catch/TFTP/bootm remoto
  docs/                    # BUILD, BOOT-TFTP, NAND-UBI, TROUBLESHOOTING...
  refs/, tree/             # DTS y parches de plataforma de referencia
logs/                      # logs seriales históricos (pueden contener datos de red)
```

`routeros-port/ros/`, `routeros-port/out/` y `routeros-port/logs/` no se
versionan. Los logs de la raíz son evidencia histórica ya publicada; revísalos
antes de reutilizarlos y no añadas IPs, MACs ni números de serie.

---

## Verificación y evidencia

El mapa no se actualiza a mano: sale de `routeros-port/progress.json` y se
regenera con:

```bash
cd routeros-port
python3 tools/progress.py
```

Cada celda equivale a un punto de peso. El total es la suma de
`peso × porcentaje`; ahora son 60/100. Un área al 100% significa que ese bloque
está verificado o implementado en el alcance actual, no que RouterOS funcione
entero.

La evidencia de hardware está en `routeros-port/docs/` y en los logs de consola.
El artefacto actual es:

| Campo | Valor |
|---|---|
| Archivo | `out/uImage-563` |
| Tamaño | 19.672.756 bytes |
| MD5 | `1a780fdd76b9da701974b17af1102be6` |
| Carga / entrada | `0x80500000` |
| Última prueba en placa | builds #29/#62; el artefacto final está pendiente |

No se debe presentar `out/uImage-563` como “probado” hasta repetir TFTP,
`bootm`, consola, UBI, `flash.ko` y shell con esa imagen concreta.

---

## Documentación

- **[PROGRESS.md](PROGRESS.md)** — informe completo: mapa, tabla de hitos,
  detalle por área, bloqueos, artefacto, historial, metodología y comandos.
- **[routeros-port/README.md](routeros-port/README.md)** — guía técnica del
  port y del arranque.
- **[Compilación](routeros-port/docs/BUILD.md)** — bootstrap, dependencias y
  verificación.
- **[Arranque por TFTP](routeros-port/docs/BOOT-TFTP.md)** — cazador, U-Boot y
  reset remoto.
- **[NAND y UBI](routeros-port/docs/NAND-UBI.md)** — geometría, BCH-4/BBT y
  montaje en lectura.
- **[Troubleshooting](routeros-port/docs/TROUBLESHOOTING.md)** — fallos típicos.
- **[Y3 / flasheo experimental](routeros-port/docs/FLASH-Y3.md)** — histórico;
  no es el método actual.
- **[Cómo contribuir](routeros-port/CONTRIBUTING.md)**.
- **[Índice de documentación](routeros-port/docs/README.md)**.

---

## Alcance legal y seguridad

- No se incluye ni se redistribuye RouterOS, el `.npk`, el rootfs ni volcados de
  NAND. No se incluye ningún *keygen*, parche de licencia o bypass.
- El arranque por defecto es **RAM/TFTP**. No escribas NAND sin un backup
  verificado y sin entender el mapa de particiones.
- Los logs pueden contener IPs, MACs o rutas de tu red. Revísalos antes de
  adjuntarlos a un issue.
- Las fuentes del kernel y los parches de MikroTik tienen su propia licencia;
  consulta `routeros-port/NOTICE.md`.

## Contribuir

Se aceptan mejoras de documentación, reproducción, diagnóstico y drivers
propios. Antes de abrir un PR lee
**[routeros-port/CONTRIBUTING.md](routeros-port/CONTRIBUTING.md)**. No adjuntes
software propietario ni resultados de licencia modificados.
