# `ROSMode::save` y el `STRONG FAIL` del `loader`

Análisis del arranque de RouterOS 7.17 `mipsbe` en el ED500 y resultado de la
prueba en placa del **2026-11-21**. La conclusión es que el mensaje
`STRONG FAIL: this is not equal to that` **no es el bloqueo**: el fallo real era
`ROSMode::save`, que necesita `/dev/jiffies`. Con ese nodo creado, `sysinit`
levanta todos los servicios y llega al login de RouterOS.

## Resumen

| Qué | Resultado |
|---|---|
| `/dev/jiffies` en el port | **no existía** |
| `ROSMode::save()` | `open("/dev/jiffies", O_WRONLY)`; sin el nodo, error |
| `saveMsg()` | escribe `/flash/rw/rosmode.msg` (137 B); **sí funciona** |
| Con `/dev/jiffies` creado | `save()` completo (104 B), servicios arriba |
| `STRONG FAIL` | se imprime, pero el `loader` sigue y arranca los servicios |
| GUI | `http://192.168.1.2/` responde **200**; el login pide contraseña |

## El binario

| Campo | Valor |
|---|---|
| Ruta | `/nova/bin/loader` |
| Tamaño | 84 684 B |
| Formato | ELF32 **MSB** (`elf32-big`), `ET_DYN` |
| Carga | base `0x400000`; `.text` en `0x4033e0` |
| `.rodata` | `0x411db0` |

`libumsg.so` es quien implementa `nv::ROSMode` (no `libuc++.so`):

| Símbolo | Dirección | Tamaño |
|---|---:|---:|
| `nv::rosMode()` | `0x77944` | 188 B |
| `nv::ROSMode::save() const` | `0x75b3c` | 200 B |
| `nv::ROSMode::saveMsg(message const&)` | `0x7b8ac` | 284 B |
| `nv::ROSMode::loadMsg(bool*)` | `0x7b6e0` | 460 B |

## La comparación del `loader`

La función que empieza en `0x40c8c0` compara cuatro palabras de su estructura
(`$s0`) con cuatro del singleton `nv::rosMode()`:

| `$s0` | `rosMode()` | Instrucción |
|---:|---:|---|
| `+144` | `+56` | `0x40dc40  beq $s1,$v0,0x40dc94` |
| `+136` | `+48` | `0x40dca0  bne $s1,$v0,0x40dc4c` |
| `+140` | `+52` | `0x40dcb4  bne $s1,$v0,0x40dc4c` |
| `+148` | `+60` | `0x40dcc8  bne $s0,$v0,0x40dc48` |

Si alguna no coincide, imprime `cerr << "STRONG FAIL: this is not equal to
that" << endl` y **devuelve normalmente**. No aborta el proceso; después el
`loader` sigue con `scheduling service startup...` y `entering run...`. En la
prueba en placa los servicios arrancaron igualmente, así que esta comparación
es una comprobación de coherencia, no el muro.

## La causa real: `ROSMode::save()`

Desensamblado (direcciones de enlace de `libumsg.so`):

```
0x75b4c  lw   $t9, -0x7118($gp)      ; open
0x75b64  lw   $a0, -0x7fd0($gp)
0x75b68  addiu $a0, $a0, 0x5600      ; "/dev/jiffies"
0x75b50  addiu $a1, $zero, 1         ; O_WRONLY
0x75b68  jalr $t9                    ; open("/dev/jiffies", O_WRONLY)
0x75b70  bgez $v0, 0x75bac           ; si fd >= 0, escribe
0x75b78  ...                         ; si no: "ERROR: ROSMode::save failed"
```

La cadena está en `libumsg.so`, bloque de datos `0x80000`: `+0x5600` es
`/dev/jiffies`, `+0x5648` el mensaje de error, `+0x57f4` `/rw/rosmode.msg` y
`+0x5804` `/nova/store/rosmode`.

En el camino correcto hace `pwrite(fd, this, 88, ...)` y comprueba que escribió
los 88 bytes; si no, vuelve al mismo error. `saveMsg()` es otra función: abre
`/rw/rosmode.msg` con `O_WRONLY|O_CREAT|O_TRUNC` y escribe el mensaje
aplanado (los **137 bytes** que aparecen en el log). Esa parte ya funcionaba.

Por eso el orden del log tiene sentido:

```
rosmode:1 wr 137                 <- saveMsg() escribe rosmode.msg
ERROR: ROSMode::save failed      <- save() no encuentra /dev/jiffies
forked
reading configuration
creating loader
STRONG FAIL: ...                 <- comprobación de coherencia
scheduling service startup...
entering run...
```

## Prueba en placa (2026-11-21)

Estado de partida: build #93, shell `~ #` dentro del `chroot`, `/flash` y el
overlay en tmpfs, NAND intacta.

1. `/dev/jiffies` no existía (`ls: No such file or directory`).
2. Se creó como fichero normal: `: > /dev/jiffies`.
3. Se lanzó `/sbin/sysinit start` completo (sin `timeout` que lo corte).
4. `ROSMode::save()` escribió **104 bytes** en `/dev/jiffies` (88 + offset 16):
   el error desapareció.
5. Arrancaron **30 procesos** `/nova/bin/*` y quedaron escuchando:

```
:::21    ftp
:::23    telnet
:::53    dns
:::80    www
:::2000  bandwidth-test
:::8291  winbox
:::8728  api
:::8729  api-ssl
```

6. La consola mostró `MikroTik  ()` y `MikroTik Login:`.
7. Desde el PC: `ping 192.168.1.2` responde y
   `curl http://192.168.1.2/` devuelve **200** con la página de RouterOS.

El `STRONG FAIL` puede seguir apareciendo en el backtrace, pero no impide el
arranque de los servicios.

### La red tras `sysinit`

`sysinit` deja las interfaces Linux abajo (`cbm0`, `lan1..lan4`) y sin IP.
Para recuperar el acceso desde el PC:

```sh
/bin/busybox ifconfig cbm0 up
for n in lan1 lan2 lan3 lan4; do /bin/busybox ifconfig $n up; done
/bin/busybox ifconfig lan4 192.168.1.2 netmask 255.255.255.0 up
```

El cable de esta prueba estaba en **lan4**; el device tree numera los puertos
del switch como `2..5` (el `0` es el de CPU), así que `lan4` es el índice 5 y
el tag `BIT(5)` es correcto.

Cuidado con las rutas: si antes se puso una IP en `lan1`, queda una ruta
`192.168.1.0/24` por `lan1` y el kernel la prefiere. Los paquetes salen por el
puerto sin cable y todo parece roto aunque el switch transmita. Hay que dejar
una sola ruta:

```sh
/bin/busybox ifconfig lan1 0.0.0.0
/bin/busybox route -n        # debe quedar solo lan4
```

Con eso, `ping` y `curl` funcionan en ambos sentidos.

### Login

La web responde, pero `admin` con contraseña vacía devuelve **401**. La API
(8728) lo muestra con precisión: con una contraseña incorrecta responde al
instante `!trap invalid user name or password (6)`; con la contraseña vacía se
queda colgada. RouterOS 7 no deja entrar con contraseña vacía por red y el
flujo de “cambie su contraseña” necesita la sesión de consola.

La consola tiene un problema añadido: el shell de inspección del initramfs y
`/bin/login` comparten `ttyLTQ0`. El login lee de byte en byte y el shell se
queda el resto de cada ráfaga, así que el usuario y la contraseña se parten
entre los dos (`admin` llega como `a` + `dmin`). Además, el login entra en un
bucle de reconexión si el servicio de consola no responde. Por eso el build
#95 arranca `sysinit` directamente (`ROS_SHELL=0`) y reserva el shell para
`ros.shell=1`.

## Cómo reproducir

Con la placa en el shell del chroot:

```sh
cp /nova/bin/loader /flash/rw/loader.bak
: > /dev/jiffies
/sbin/sysinit start
```

Después, si hace falta red:

```sh
/bin/busybox ifconfig cbm0 up
for n in lan1 lan2 lan3 lan4; do /bin/busybox ifconfig $n up; done
/bin/busybox ifconfig lan4 192.168.1.2 netmask 255.255.255.0 up
```

`/dev/jiffies` y las interfaces viven en tmpfs/devtmpfs: se pierden al
reiniciar. El init de este árbol (`init-initramfs.sh`) ya crea
`$R/dev/jiffies` antes de ceder el control a `sysinit` y arranca `sysinit`
directamente; el shell de inspección queda detrás de `ros.shell=1`. El build
#95 incluye ambos cambios y un ayudante `netup` que, cuando RouterOS ya ha
arrancado, levanta `cbm0`/`lan4` y pone `192.168.1.2` para validar web/API sin
shell. Está pendiente de probar en placa.

## Incidente del 2026-11-21

Durante las pruebas de consola la placa quedó **haltada**. El shell de
inspección y `/bin/login` compartían el mismo tty; al intentar recuperar el
control se envió un BREAK y la placa dejó de responder por serie y por red. El
PHY sigue enlazado a 1 Gbps, así que hay alimentación, pero no queda ningún
proceso vivo desde el que ejecutar el reset por RCU. No se escribió la NAND.
Para continuar hace falta un ciclo de corriente y tener armado
`catch_final.py` o `uboot_cycle.py` antes de que U-Boot autoarranque la NAND.

## Aviso para trabajo remoto

La consola serie es el único canal de recuperación. Antes de cualquier paso que
pueda reiniciar la placa hay que tener armado `catch_final.py` o
`uboot_cycle.py watch`: U-Boot autoarranca la NAND en `bootdelay=3` y, sin
cazador, recuperar el prompt exige cortar la corriente.

Las pruebas de este documento no reiniciaron la placa: `sysinit` se lanzó desde
el shell, que sobrevivió, y la NAND no se escribió.

## Herramientas

`objdump` de la toolchain no soporta MIPS; para estos binarios están:

```bash
python3 tools/mipsdis.py ros/rootfs/lib/libumsg.so --va 0x75b3c --fin 0x75c04
python3 tools/gotlook.py ros/rootfs/lib/libumsg.so --funcion 0x75b3c:0x75c04
```

`mipsdis.py` desensambla y busca inmediatos; `gotlook.py` resuelve cada
`lw $t9, -N($gp)` contra `.rel.dyn`/`.dynsym`, que es lo que permitió identificar
`open`, `pwrite`, `close`, `Store::set` y compañía sin ejecutar el binario.

## Alcance

Análisis de binarios que ya están en el equipo y prueba en hardware propio,
para entender por qué no arrancaban los servicios. No es un parche de licencia
ni un bypass: la licencia se acepta antes de este punto
(`RouterOS is now licensed`) y no se redistribuye ningún binario de MikroTik.
