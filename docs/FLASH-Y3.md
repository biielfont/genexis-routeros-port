# Instalar por la web / U-Boot con un `.y3` propio

> **Estado: experimental / histórico (nov 2026).** Este documento describe la
> investigación del contenedor `.y3` y el camino de instalación persistente.
> **No se ha flasheado en hardware** y no es el método actual. El método
> soportado es **TFTP a RAM** ([BOOT-TFTP.md](BOOT-TFTP.md)); la NAND solo debe
> tocarse con backup y plan de recuperación ([NAND-UBI.md](NAND-UBI.md)).

## 1. El formato ya está descifrado

Un `.y3` del ED500 es **cabecera de texto de 1024 bytes + rootfs UBIFS + pkginfo + MD5**.
Cabecera real del firmware oficial `GNX-4.3.6.170-R`:

```
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
sig 0          <-- NO hay firma criptografica
md5ofs 44978870
md5 32
size 44978902
```

Dos hechos comprobados, no supuestos:

- `sig 0`: **el update no verifica ninguna firma**, solo un MD5 en ASCII.
- El MD5 cubre todo desde el byte 0 hasta `md5ofs`. Reconstruir el firmware
  oficial con nuestra herramienta da un fichero **idéntico byte a byte** al de
  Genexis, así que el contenedor está perfectamente entendido.

Herramienta: `08-y3tool.py`

```
python3 08-y3tool.py info   out/ED500-stock-original.y3
python3 08-y3tool.py unpack out/ED500-stock-original.y3 /tmp/ext
python3 08-y3tool.py build  nuevo.y3 --ubifs rootfs.ubifs --pkginfo pk.txt \
        --release GNX-4.3.6.999-R
```

Geometría del rootfs (deducida del UBIFS oficial y respetada al construirlo):
PEB 128 KiB, LEB 124 KiB (`126976`), página 2 KiB. Eso encaja con la NAND
**Macronix MX30LF1G18AC** (1 Gbit SLC, 2 KiB de página, 64 B de OOB, 128 MiB)
cuyo ID es justo el `0xc2 0xf1` que canta tu U-Boot.

## 2. Qué hay en `out/`

| Fichero | Qué es |
|---|---|
| `ED500-stock-original.y3` | firmware oficial de referencia (44,9 MB) |
| `ED500-stock-reconstruido.y3` | **idéntico byte a byte** al oficial, salido de nuestra herramienta |
| `ED500-nuestro-kernel.y3` | rootfs UBIFS mínimo con nuestro kernel (`/boot/uImage`, `/uImage`, `/kernel`) |

El tercero es el interesante: 10 MB, `release GNX-4.3.6.999-R` (número alto para
pasar cualquier comprobación de versión), mismo `board`/`chip`/`model` que el
oficial, MD5 correcto y sin firma. Al arrancar, el kernel lleva su initramfs
dentro: no necesita el resto del rootfs para dar shell.

## 3. Procedimiento seguro en dos pasos

**Paso 1 — validar el contenedor sin riesgo.** Sube `ED500-stock-reconstruido.y3`
por la web (JUCI → Firmware) o por U-Boot:

```
setenv serverip <IP de tu PC>
# copia el fichero a tu carpeta TFTP con el nombre last.y3
run update_image
```

Como su contenido es idéntico al firmware oficial, si el router reinicia normal
sabemos que nuestro contenedor pasa el update. Si algo va mal aquí, no hemos
perdido nada: es el mismo firmware que ya tenía.

**Paso 2 — nuestro kernel.** Repite con `ED500-nuestro-kernel.y3`. Si el cargador
lee el kernel de un fichero dentro del rootfs (que es lo que sugiere que el
firmware oficial lleve un `uImage` dentro del UBIFS), arrancará nuestro 5.6.3 y
verás el banner por `ttyLTQ0`.

## 4. Lo que todavía no sé y necesito del router

El U-Boot de Genexis es a medida (`primary system is 1`, `run update_image`,
`Type run flash_nfs…`). En su entorno hay definido **cómo** carga el kernel
(qué volumen, qué ruta y en qué dirección). Eso no está en ningún fichero
público: hay que leerlo del equipo con:

```
printenv
```

Lo que busco: la definición de `update_image` y de `bootcmd` (líneas con
`ubifsload`, `ubi write`, `bootm`, `rootfs_0`/`rootfs_1`). Por eso el rootfs que
he construido lleva el kernel en tres rutas plausibles (`/boot/uImage`,
`/uImage`, `/kernel`); con el `printenv` lo dejo en la ruta exacta.

## 5. Si sale mal

El equipo tiene dos bancos (`rootfs_0` / `rootfs_1`) y un contador de arranques:
un rootfs roto no borra el otro. Y en el peor caso está el modo ROM por UART
(puente en los dos contactos + cargar U-Boot en RAM), documentado en el repo
`biielfont/Genexis-Pure-ED500/uboot/`.

Antes de flashear: **desconecta el WAN**. Si el router arranca y ve TR-069, el
ISP puede reescribir el firmware por su cuenta.

## 6. Aviso honesto sobre "acabar en MikroTik"

El `.y3` resuelve el *cómo se instala*: un contenedor sin firma que el router
acepta. Lo que no resuelve es *qué se instala*. RouterOS no tiene soporte para
el GRX350: los `.npk` mipsbe son para placas MikroTik y su userland no trae
drivers de este SoC (ni NAND, ni switch, ni PHY). Aunque arrancase el kernel con
`board=norrland`, RouterOS se quedaría sin red y sin flash.

Lo que sí es realista, y es lo que estamos construyendo: **Linux/OpenWrt
funcionando en el ED500**, instalable desde la web con este `.y3`. Si el
objetivo final es "RouterOS o nada", el cuello de botella no es el arranque, es
que MikroTik no escribió drivers para este chip.

## 7. Modo headless (sin cable serie)

> **Actualización 2026-11:** el port actual sobre 5.6.3 ya trae Ethernet Linux
> (DSA/GSWIP + PHY XWAY) y se usa por TFTP. El comentario de "no hay driver" de
> este apartado se refiere al contenedor 6.18/headless antiguo, no al estado
> actual del repo.

La initramfs arranca red y servidores por sí sola:

- pide IP por **DHCP**; si en 8 s no hay concesión, se pone **192.168.1.2/24**
  con gateway 192.168.1.1,
- levanta **httpd en el puerto 80** con una página de estado,
- **telnetd en el 23** (root sin contraseña) y **SSH en el 22** si dropbear
  compiló,
- y deja la shell en `ttyLTQ0` como siempre.

La página (`http://<ip>/`) se refresca sola cada 5 s y el CGI
`/cgi-bin/status` devuelve texto plano con: host, kernel, uptime, una lista de
comprobaciones (`[ok] kernel`, `[ok] proc`, `[ok] cpus`, `[ok] memoria`,
`[ok] red eth0 …`), memoria, interfaces y las últimas 60 líneas de `dmesg`.

Probado en QEMU con una NIC `e1000` real emulada:

```
red: 10.0.2.15 en eth0
web: http://10.0.2.15/
telnet: puerto 23 (root, sin password)

=== ESTADO ===
[ok] kernel en ejecucion
[ok] proc montado
[ok] cpus detectadas
[ok] memoria: 246 MiB
[ok] red eth0 10.0.2.15/24
```

**Lo que falta en el ED500 real:** el kernel ya trae la pila de red
(`CONFIG_NET`, `INET`, `PACKET`, DHCP), pero **no hay driver Ethernet para el
GRX500**. El switch del SoC (`GRX500-Switch` en el U-Boot) necesita el driver
CBM/DQM + switch, que es justo el bloque H2c. Sin él no aparece `eth0`, la
initramfs lo dice por consola (`red: no hay interfaces`) y no hay página que
visitar: en hardware, hoy, la única salida es el cable serie.

Cuando ese driver entre, este `.y3` ya lleva la imagen headless dentro: se
flashea y la página aparece sin tocar nada más.

## 8. Base 6.18 con Ethernet (en pruebas)

`out/ED500-net618.y3` (34,5 MB) es el primer contenedor con un kernel que **sí
trae driver Ethernet**: el árbol 6.18 de grische (`intel-mips-xrx500-v6.18`),
que es el que funciona en el FRITZ!Box 7560 con este mismo GRX350.

Qué lleva dentro, verificado sobre el binario:

- `CONFIG_INTEL_XRX500_NET=y`, `INTEL_XRX500_BM=y` → CBM/FSQM, TMU, HDMA y el
  conduit del CPU compilados y enlazados (3 símbolos de probe presentes).
- DTB `norrland` **embebido** en la sección `.dtb.init.rodata`
  (`__dtb_start=0x81390960`, `__dtb_end=0x81392ca8`, 9032 bytes): el U-Boot de
  Genexis no pasa DTB, así que `prom.c` usa `__dtb_start`.
- Initramfs headless (DHCP/IP fija + web de estado + telnet).
- `uImage` con `-a 0x80500000 -e 0x8107484c` (entry del ELF).

Lo que **no** puedo garantizar: nunca se ha arrancado. El DTS es mínimo (el del
SoC + memoria y consola); las partes de placa que sus drivers esperan — reserva
de memoria para el firmware del GPHY, numeración de puertos, PHY addresses,
LEDs — están en `seale_avm.dtsi` para las FRITZ y aquí no existen. Si el switch
no encuentra su firmware de GPHY, `eth0` no aparecerá aunque el driver esté
compilado.

Orden recomendado de pruebas: `ED500-stock-reconstruido.y3` (cero riesgo) →
`ED500-net618.y3` → y si no vuelve, el otro banco arranca el stock solo.
