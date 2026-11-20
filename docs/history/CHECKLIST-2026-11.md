# Primera prueba de arranque del 5.6.3 en el ED500

> **Documento histórico (nov 2026).** Es el checklist de la primera puesta en
> marcha y la auditoría previa. Algunas secciones (NAND, rootfs, licencia) ya
> se avanzaron después. Para el estado actual usa [../BOOT-TFTP.md](../BOOT-TFTP.md)
> y el [estado actual](../PROGRESS.md).

## Antes de encender (5 minutos)

1. **Cable de consola**: COM4, 115200 8N1. Es el punto que falló la última vez
   (la placa estaba encendida y muda, pero por el kernel sin consola, no por el cable).
   Comprobar que responde: con el router apagado no hay eco; al encender debe salir
   `ROM VER: 2.1.0`.
2. **Cable de red**: PC en cualquier boca LAN (`lan1..lan4`). Da igual cuál: el init
   las puentea todas en `br0`.
3. **TFTP**: el servidor escucha en `0.0.0.0:69` con raíz `routeros-port/out`.
   Comprobar que `uImage-563` está ahí y pesa lo que toca.
4. **PC**: IP estática `192.168.1.160/24` en la interfaz Ethernet (ya configurada).

## Arranque

Encender y, durante los 3 segundos de `bootdelay`, mandar CR para cortar el autoboot.
Debe aparecer `IOPSYS 2 grx500 #`. Entonces:

```
tftpboot 0x80500000 uImage-563
bootm 0x80500000
```

Si no se caza el prompt: apagar, encender y martillear CR (lo hace `catch_final.py`).

## Qué debe salir por consola, en orden

1. `Linux version 5.6.3` — el kernel correcto (el de fábrica dice 4.9.109).
2. `Console: colour dummy device` / `console [ttyLTQ0] enabled` — consola viva.
3. `gswip-xrx500 1c000000.switch: probed GSWIP version ...` — el switch portado.
4. `DSA: tree 0 setup` y `lan1..lan4` — puertos del switch.
5. `cbm` / `xrx500-conduit` — el conduit que da salida al CPU.
6. `red: puertos: ...` y `red: 192.168.1.2 en br0` — el init configuró la red.
7. `web: http://192.168.1.2/` y `telnet: puerto 23`.
8. Prompt `~ #`.

## Cómo entrar si la consola falla otra vez

Desde el PC, sin tocar nada:

```
ping 192.168.1.2
telnet 192.168.1.2        # root, sin contraseña
http://192.168.1.2/       # página de estado
```

## Señales de problema y qué significan

| síntoma | causa probable |
|---|---|
| Nada en consola, pero enlace 1 Gbps | kernel sin consola o UART desconectada |
| `ROM VER` en bucle | la entry del uImage no es la del ELF |
| Arranca y no hay `lan*` | el driver GSWIP no enlazó (ver dmesg) |
| `lan*` pero sin `cbm0` | el conduit no probeó (memoria reservada o DMA) |
| `br0` sin IP | el switch no reparte y el bridge se quedó sin puertos |
| `request_firmware` falla | firmware del PHY (va embebido y en /lib/firmware) |

## Después del arranque (objetivo real: RouterOS)

Si el kernel levanta y hay red, el siguiente paso es darle **su rootfs** (el squashfs
del npk original) en vez de nuestro initramfs. Eso exige UBI/UBIFS o montarlo por NFS,
y es el paso previo a ver `/nova` y WebFig.

## Fallos ya corregidos de antemano (auditoría previa)

Estos cinco habrían dado la cara mañana y ya están resueltos en `out/uImage-563`:

| fallo | consecuencia | arreglo |
|---|---|---|
| `CONFIG_SERIAL_LANTIQ` no existía | consola muda | Kconfig `LANTIQ \|\| INTEL_MIPS` |
| `CONFIG_BRIDGE` apagado | sin bridge, IP en una boca al azar | activado |
| busybox sin `ip`, `awk`, `wc` | init fallaba en silencio, sin IP | init reescrito con `ifconfig`/`route`/`brctl` |
| firmware del GPHY ausente | puertos sin enlace | embebido + `/lib/firmware/lantiq/` |
| sin driver de relojes GRX500 | ASC en `-EPROBE_DEFER` para siempre | portado `clk-grx500` + CGU desde 6.18 |

El `earlycon=lantiq,0x16600000` de los bootargs no depende de nada de eso: si el
resto falla, al menos se ve por dónde va el arranque.

## Tercer bloque: cadena de arranque verificada a mano

Comprobado byte a byte antes de encender:

- `uImage-563`: magic `27051956`, CRC de cabecera **y** de datos válidos, `os=Linux`,
  `arch=MIPS`, `type=kernel`, sin comprimir, carga = entrada = `0x80500000`.
- El payload arranca en `kernel_entry` (`sync; ehb; mfc0 t1,c0_config`), no es un ELF.
- DTB embebido: `__dtb_end - __dtb_start` = **11.296 B**, exactamente `norrland.dtb`.
- Timer: `intel-mips/time.c` saca `mips_hpt_frequency` del reloj del nodo CPU
  (`<&cgu 150>` = `CLK_CPU`), y el driver CGU lo registra. Sin eso no hay clocksource.
- Consola: `lantiq,asc` con relojes `<&cgu 13>` y `<&cgu 117>`, ambos registrados.
- `/init` dentro del cpio es **0755**; busybox tiene `sed`, `cut`, `grep`, `ifconfig`,
  `brctl`, `route`, `udhcpc`, `httpd`, `telnetd` y `dmesg` compilados.

**Tag de DSA portado**: el XRX500 mete una cabecera de 8 bytes en el puerto CPU, pero
DSA solo tenía el tag `gswip` de 4. Se ha portado `tag_gswip3` (enum, driver, Kconfig)
 y el switch ya declara `DSA_TAG_PROTO_GSWIP3`. Sin esto los puertos saldrían pero la
red no pasaría ni un paquete.

## Quinto bloque: mapa de memoria aclarado (no era un bug)

Parecía raro cargar en `0x80500000` mientras el DTB dice que la RAM está en
`0x20000000`. Comprobado con el kernel de fábrica: **carga en `0xa0020000`**, o sea
físico `0x20020000`. En este SoC con EVA, KSEG0/KSEG1 mapean a partir de
`0x20000000`, así que `0x80500000` es físico `0x20500000`, dentro de la RAM.
Todo coherente: `mem=224M@512M`, `memory@20000000` y nuestra dirección de carga.

El kernel ocupa `0x20500000`–`0x20B6_7000` (6,7 MB) y el pool del CBM empieza en
`0x23800000`: 33 MB de margen, no hay solape.

**Reinicio resuelto**: el DTB trae un nodo `reboot` con `compatible =
"syscon-reboot"` (hijo del chiptop, offset 0x10, bit 0x40000000). Con
`CONFIG_POWER_RESET` + `CONFIG_POWER_RESET_SYSCON` activados, `reboot` funciona y,
como los bootargs llevan `panic=20`, un panic **reinicia la placa sola**. El cazador
vuelve a esperar U-Boot, así que un fallo se reintenta sin tocar la corriente.

Si `syscon-reboot` no acertara con el registro, el reboot no haría nada (no rompe
el arranque). En ese caso, cada intento vuelve a necesitar un corte de corriente.

## Cuarto bloque: el arranque ya está probado en seco

- **TFTP integrado en el cazador**: `catch_final.py` sirve la imagen él mismo
  (puerto 69 y, si está ocupado, 6969 + `setenv tftpdstp`). Probado con un cliente
  real: descarga de 6.702.516 bytes, **idéntica byte a byte**.
- **Direcciones fijadas antes de cargar**: `setenv ipaddr 192.168.1.1` y
  `setenv serverip 192.168.1.160`, para no depender de lo que quedara en el entorno
  de U-Boot. La Ethernet del PC tiene además alias en 192.168.0/30/31/32.160.
- **Reintento automático**: si el kernel se reinicia, el cazador vuelve a esperar
  U-Boot y recarga, hasta agotar la ventana de 3 h.
- **Log por web**: el init deja `/www/dmesg.txt` y `/www/estado.txt`. Sin consola,
  `http://192.168.1.2/dmesg.txt` da el arranque completo.
- **Veredicto automático**: al terminar, el cazador imprime en una línea qué ha
  pasado (`arranco + switch + lan1 + red + http + shell`, `PANIC`, o
  `bootm mudo`), sin tener que leer el log entero.
- **`ignore_loglevel`** en los bootargs: el kernel imprime también los mensajes de
depuración desde el primer instante.
- **Corregido un fallo mío**: el init metía `eth0` (maestro de DSA) en el bridge
  junto a sus propios puertos, lo que rompe el datapath. Ahora usa solo `lan*` y
  solo cae en `eth*`/`cbm*` si no hay puertos DSA.

## Segundo bloque: lo que RouterOS necesitaba del kernel

El kernel compilaba, pero la configuración no servía para un userspace real. Estos
seis estaban **apagados** y habrían matado `/nova` en el primer segundo, sin mensaje:

| opción | sin ella |
|---|---|
| `CONFIG_FUTEX` | no hay hilos: cualquier binario con pthreads muere |
| `CONFIG_EPOLL` / `EVENTFD` / `TIMERFD` / `SIGNALFD` | el bucle de eventos de `/nova` no arranca |
| `CONFIG_POSIX_TIMERS` / `AIO` | temporizadores y E/S asíncrona |
| `CONFIG_NETFILTER` / `NF_CONNTRACK` | el firewall no puede engancharse |
| `CONFIG_MIPS_FP_SUPPORT` | SIGILL si algún binario usa la FPU |
| `CONFIG_TMPFS` / `SHMEM` | sin `/dev/shm` ni `/tmp` en RAM |
| `CONFIG_SQUASHFS`+`XZ`, `BLK_DEV_LOOP` | no se puede montar su rootfs |
| `CONFIG_IP_MULTIPLE_TABLES` | RouterOS enruta con tablas: sin esto, no hay rutas |

Un initramfs con busybox no usa nada de eso, así que el fallo no se habría visto
hasta meter el rootfs de RouterOS dentro. Ya están todas en `y`.

## Pendiente para el rootfs real de RouterOS

1. **NAND**: el árbol 5.6.3 no trae `lantiq-xrx500-nand.c` (sí el 6.18). Para montar
   su rootfs desde la flash hay que portarlo. Alternativa sin NAND: meter su árbol
   de ficheros en el initramfs y hacer `switch_root`.
2. **vermagic**: nuestro kernel dice `5.6.3 mod_unload MIPS32_R2 32BIT`. Si sus `.ko`
   se compilaron con SMP/preempt, no cargarán hasta compilar un kernel con esos flags.
3. **Licencia**: `/nova` puede pedir licencia atada al hardware. Ahí se para, sin parchear.

## Rollback

Nada de esto escribe en NAND: `tftpboot` + `bootm` van a RAM. Para volver al
firmware de fábrica, quitar la corriente y dejar que arranque solo.
