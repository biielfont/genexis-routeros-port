# Hardware del ED500: reset, LEDs e instalación en NAND

El build **#102** (`out/uImage-563`, 21.899.532 B, MD5
`e2e8698843a1278da58e5d9178c89f5a`) añade la instalación persistente,
desbloquea los módulos propietarios (el kernel exporta sin GPL-only las APIs
que usan `switch.ko`, `phy_helper.ko`, `flash.ko`, etc.) y da a los puertos
DSA `ros-name = "ether1..4"`, que es lo que `net` usa para crear las
interfaces RouterOS. Además, el autorun y `netup` prueban `ether1..4` y
`lan1..4`, así el bridge no queda vacío si `net` renombra los puertos. El
`.y3` `out/ED500-routeros-7.17-nand.y3` lleva el kernel y el DTB para `rootfs_0`
y el init monta `/flash/rw` en NAND y resetea el flag `boot_cnt_primary` de
U-Boot. **Un solo banco activo**: `rootfs_0`; `rootfs_1` no se monta ni se
arranca, solo queda como copia stock de recuperación manual.

**Todavía no se ha flasheado**: la placa quedó haltada y la próxima prueba es
el lunes. El build #97 (reset/LEDs) tampoco se ha probado en placa. Hasta
entonces, esto es implementación compilada y verificada a nivel de contenedor,
no hardware verificado.

## Mapa de hardware

Los datos salen del *board database* stock del ED500, no de los LEDs genéricos
del DTS de Intel.

| Función | GPIO / bus | Polaridad | Uso |
|---|---|---|---|
| Reset | GPIO0 pin 0 (`addr 480`) | activo a bajo | 5 s para reiniciar |
| WPS | GPIO0 pin 10 (`addr 490`) | activo a bajo | reservado; no se usa todavía |
| LEDs Ethernet verdes | SSO pines 0–4 | hardware | `led0`–`led4`, `green:gphy` |
| LEDs Ethernet amarillos | SSO pines 8–12 | hardware | `led8`–`led12`, `yellow:gphy` |
| LEDs panel | SSO pines 5–7, 13–14 | software | CATV, wireless, voice, internet, uplink |
| LED RGB | SK9822 en GPIO1 15/14 | bit-bang | `/sys/devices/platform/canyon_led/sk9822/led_color` |

El GPIO global `480` del board DB corresponde a **GPIO0 pin 0**; `490` es
GPIO0 pin 10. El driver usa el *phandle* del DTS, no el número global, para no
depender del orden en que se registren los `gpiochip`.

## Qué añade el build #97

- `kernel/ed500-buttons.c`: consulta el reset cada 100 ms y llama a
  `kernel_restart("ed500-reset")` tras 5 s pulsado.
- `kernel/leds-intel-sso.c`: driver SSO compacto. Usa `SSO_CPU`,
  `SSO_CON1`/`SSO_CON3` y los *duty cycles* de 0x8 a 0x84; registra los LEDs
  como `/sys/class/leds/ledN:...`. Habilita `GCLK_SSO` y el reloj `fpid` de
  100 MHz.
- `kernel/leds-sk9822.c`: bit-bang sobre GPIO1 15/14; atributo `led_color` con
  el nombre de plataforma `canyon_led`.
- `drivers/net/phy/intel-xway.c`: `LEDCH=0x10`, `LEDCL=0`, `LED0H=0x40`
  (1000M), `LED1H=0x30` (10/100M) y `reg 0x1b=0x7f00`, sin parpadeo.
- `drivers/pinctrl/pinctrl-equilibrium.c`: *compatible*
  `intel,pinctrl-xrx500` y `request`/`free` por pinctrl. Sin eso los bancos
  `gpio@16c00000`/`gpio@16c00100` no se registran.

## Qué añade el build #98/#99 (NAND)

- **`.y3` instalable**: `out/ED500-routeros-7.17-nand.y3`, 53.613.270 B, MD5
  `3e9b37d712ad6610bbaa2dc7d7ae2ccb` (reempaquetado en el #102 con el kernel
  que exporta sin GPL-only, el DTB con `ros-name`, el autorun que prueba
  `ether1..4`/`lan1..4` y el ABI de `struct net_device` corregido). Contiene
  una UBIFS de 422 LEBs con
  `/boot/uImage`, `/boot/norrland.dtb`, `/rw` y un `pad` de 30 MB.
- **Arranque sin TFTP**: U-Boot `iboot` monta `rootfs_0` y carga
  `/boot/uImage` + `/boot/norrland.dtb`; `bootm` arranca el kernel.
- **`/flash/rw` persistente**: el init monta **`rootfs_0`** en rw en `/nand`
  y enlaza `/flash/rw` → `/nand/rw`. La config, logs y estado de RouterOS
  sobreviven al reinicio. Antes era tmpfs.
- **Flag de arranque**: `bootok` espera a que la web/API responda y ejecuta
  `fw_setenv boot_cnt_primary 0`, como `/etc/init.d/bootcount` del stock.
  Sin esto `iboot` acabaría intentando el banco de recuperación tras varios
  reinicios. No hay lógica A/B ni se toca `boot_cnt_alt`.
- **`clk_ignore_unused` por defecto** en el kernel (el bootargs de NAND no lo
  trae) y `panic=20` en el init.
- **Autorun de primer arranque**: la contraseña de `admin` se fija solo la
  primera vez; después el autorun persistente se respeta y el `bootok` borra
  esa línea para no pisar cambios.

Detalle del contenedor, instalación y verificación:
**[FLASH-Y3.md](FLASH-Y3.md)**. Mapa de volúmenes:
**[NAND-UBI.md](NAND-UBI.md)**.

## Comprobación en placa (lunes)

Antes de tocar NAND, ejecuta en WSL/Linux:

```bash
bash tools/verify-offline.sh
```

No abre `/dev/mtd` ni `/dev/ubi`. Cubre el `.y3`, la UBIFS, el initramfs, el
entorno U-Boot redundante, el `bootok` en `rootfs_0` (y que `rootfs_1` se
ignora) y la recuperación stock. Después, consola a 115200 8N1: primero
arranque TFTP para comprobar que el kernel #102 sigue vivo; luego, la
instalación NAND.

### 1. Arranque TFTP (sin escribir NAND)

```bash
python catch_final.py --horas 6
```

Comprobar en consola:

```sh
dmesg | grep -Ei 'eqbr|pinctrl|sso|sk9822|ed500|reset button'
cat /sys/kernel/debug/gpio
ls /sys/class/leds

echo 255 > /sys/class/leds/led13:green:internet/brightness
echo 0   > /sys/class/leds/led13:green:internet/brightness
echo ff0000 > /sys/devices/platform/canyon_led/sk9822/led_color
echo 00ff00 > /sys/devices/platform/canyon_led/sk9822/led_color
echo 0000ff > /sys/devices/platform/canyon_led/sk9822/led_color
```

Reset: mantener 5 s; la consola debe mostrar
`reset button held for 5000 ms, restarting`.

> Con TFTP, el botón reinicia pero U-Boot vuelve a la NAND stock si no hay
> cazador armado. Para que el reset vuelva al port, deja
> `catch_final.py --seguir` o `uboot_cycle.py watch` esperando antes de
> pulsarlo.

### 2. Instalación NAND

**Vía U-Boot (única; un solo banco):** copia el `.y3` como `last.y3` en el
TFTP y:

```text
setenv serverip 192.168.1.161
run update_image
setenv root_vol rootfs_0
setenv boot_cnt_primary 0
setenv boot_cnt_alt 0
saveenv
reset
```

`run update_image` escribe **`rootfs_0`** y fija `root_vol=rootfs_0`. No se usa
la web stock ni el banco siguiente. Para volver a Genexis, repite con
`out/ED500-stock-original.y3` como `last.y3`.

### 3. Primer arranque desde NAND

Sin TFTP, la consola debe mostrar:

```text
Booting kernel from Legacy Image ...
Linux version 5.6.3 ...
--- RouterOS: montando rootfs ---
  NAND: rootfs_0 montado rw en /newroot/merged/nand
  /flash/rw: NAND
  flag de arranque U-Boot: ayudante bootok armado
...
```

Comprobar:

```sh
mount | grep -E 'nand|flash'
ls -l /flash/rw
cat /flash/rw/bootok.log
# La config debe sobrevivir:
echo hola > /flash/rw/prueba-nand
# reiniciar sin TFTP
cat /flash/rw/prueba-nand
```

Y el contador:

```sh
fw_printenv -c /flash/rw/fw_env.config boot_cnt_primary boot_cnt_alt
```

El único flag que debe bajar es `boot_cnt_primary`, porque `rootfs_0` es el
único banco activo. `boot_cnt_alt` no se toca. Si `bootok.log` dice
`fw_printenv no lee root_vol`, el tool no está leyendo los volúmenes UBI
`env1`/`env2`: revisar `ubiattach` y `fw_printenv` antes de seguir.

### 4. Si algo falla

- **No arranca el port:** no hay fallback automático a un segundo sistema.
  Entra en U-Boot con `catch_final.py` y vuelve a Genexis con
  `out/ED500-stock-original.y3` como `last.y3` y `run update_image`; o
  reinstala el `.y3` del port. `rootfs_1` no se arranca solo.
- **Arranca pero no hay `/nand`:** el bootargs de NAND trae
  `ubi.mtd=ubi,0,30`; el init adjunta con `-O 2048`. Mirar
  `dmesg | grep ubi` y `cat /proc/mtd`.
- **La web no responde:** `netup` crea `br0`/IP si RouterOS no lo hace;
  `/flash/rw/netup.log`. La contraseña inicial es `ed500` en el primer
  arranque; cámbiala en RouterOS.
- **El contador no baja:** `fw_setenv` necesita que UBI esté adjunto y
  `fw_env.config` apunte a `/dev/ubi0:env1`/`env2`. El `bootok` solo actúa si
  sysinit responde.

## Netinstall y actualización web

### Netinstall oficial

**No funciona con el bootloader actual.** MikroTik Netinstall necesita que el
equipo ejecute **RouterBOOT en modo Etherboot**: RouterBOOT pide IP por BOOTP,
descarga el instalador por TFTP y escribe la flash. El ED500 trae el
**U-Boot de Genexis**, que no implementa Etherboot ni RouterBOOT. No es un
problema de configuración del servidor Netinstall.

No intentes arrancar un RouterBOOT de otra placa MikroTik: está hecho para
otro hardware y puede dejar el equipo sin arranque. La vía segura es U-Boot +
`.y3` (instalación) o TFTP a RAM (prueba), documentada en
[FLASH-Y3.md](FLASH-Y3.md) y [BOOT-TFTP.md](BOOT-TFTP.md). Eso no es
Netinstall.

### WAN xDSL (VRX518), no GPON

El firmware stock extraído (`GNX-4.3.6.170-R`) es **xDSL**: trae `vrx518.ko`,
`vrx518_tc.ko`, `drv_dsl_cpe_api.ko` y `/etc/init.d/dsl`, y **ningún** módulo
PON/OMCI. La afirmación anterior de "ED500 GPON" era incorrecta para esta
unidad. RouterOS no trae driver VRX518 y el de Genexis es binario para
4.9.109, así que **la WAN xDSL no se puede usar desde RouterOS**. El kernel
Linux lleva la Ethernet DSA/GSWIP, que es la red de gestión/LAN; un router
MikroTik completo necesitaría también un driver VRX518, que no está en las
fuentes GPL. No es un problema de configuración.

### Actualización desde WebFig

Antes no podía persistir porque `/flash` era tmpfs y la NAND solo se leía.
Con el `.y3` instalado, `/flash/rw` es un directorio de `rootfs_0` en NAND:
la configuración y los logs sí persisten. Un `.npk` de actualización de
RouterOS sigue sin poder aplicarse como en un RouterBOARD real: el rootfs es
el squashfs del initramfs y no hay un instalador de paquetes que escriba en
la NAND. Para cambiar de build, se reconstruye el `.y3` y se reinstala.

Las alternativas reales son:

1. **`.y3` en NAND (actual):** instala kernel + DTB + `/flash/rw` persistente.
2. **TFTP a RAM:** para probar un kernel nuevo sin tocar la NAND.
3. **USB:** no implementado; el kernel actual no trae el soporte verificado.

## Seguridad

- No escribas NAND sin backup y sin el cable serie.
- El `.y3` no lleva firma; el update solo comprueba el MD5. Un `.y3`
  corrupto se rechaza, pero uno mal construido puede dejar el banco sin
  arranque. El otro banco sigue siendo la red de seguridad.
- No redistribuyas el rootfs de RouterOS ni el firmware de Genexis.
