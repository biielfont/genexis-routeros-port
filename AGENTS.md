# Instrucciones del proyecto

- Al terminar cada conversación, hacer commit de los cambios y `push` a `origin/main`, incluyendo los logs relevantes.
- Estado vivo y registro de pruebas de la placa: el resto de este archivo.

---

# AGENTS.md — Estado vivo: RouterOS 7.17 en Genexis Pure ED500

> **Lee este archivo al empezar cada sesión.** Si cambias de modelo o de agente,
> esto es lo último que se hizo, qué está armado y qué está validado.
>
> **Última actualización:** 2026-11-26 (sesión H14…H47). Imagen actual: **H47**,
> `out/uImage-563`, **23.950.632 B**, BUILD_RC=0, `ROS_POST=0`, autorun con
> `/user set admin password="__ROSPASS__"`, sin `userseq.console`.
>
> **Regla de oro:** no se declara "arreglado" sin consola/login en la placa.
>
> **2026-11-27 — H48: CAUSA RAIZ ENCONTRADA Y PARCHEADA (defconf).**
> El `SCRIPT ERROR: interrupted` lo imprime `/sbin/sysinit` en `0x404854`
> (unico sitio del rootfs con ese literal) y **solo** despues de ejecutar un
> script por RPC: `nv::message` con timeout de **12000 ms**
> (`addiu $a3,$zero,0x2ee0`, `0x4047c0`). Los tres unicos llamantes son los
> scripts de configuracion por defecto:
> `/nova/lib/defconf/get-custom-defconf`, `defconf` y
> `defconf-caps`/`defconf-wps-sync`. `get-custom-defconf` espera en bucle
> **hasta 30 s** a que exista una interfaz `loopback`
> (`:while ([:len [/interface find where type="loopback"]] = 0 && $count < 30)`);
> `defconf-caps`/`defconf-wps-sync` esperan igual a `ethernet`. En este
> arranque esas interfaces no aparecen, el script pasa del timeout de 12 s,
> sysinit lo interrumpe y el motor de scripts devuelve `interrupted`.
> **H48 vacia los cuatro scripts antes de `switch_root`** para que terminen
> al instante. Imagen `out/uImage-563`, **23.951.696 B**, MD5
> `5f6a7e955f8215e09bdfb4eefc6a6fd1`, BUILD_RC=0. **Pendiente de placa.**
>
> **ESTADO 12:35 — H12 ejecutada. CAUSA RAÍZ IDENTIFICADA: `loader` no puede
> leer `/dev/mtdblock18`; H13 construida con el enlace, falta ciclo de corriente.**
>
> **H12 (arranque real, 11:57) — `loader12.diag` da el error exacto:**
> ```
> forked
> reading configuration
> creating loader
> readMBR: could not open /dev/mtdblock18: 2
> Failed to read MBR:/dev/mtdblock18
> ```
> Es decir, `loader` abre `/dev/mtdblock18` (la partición de tipo `hard_config`
> en el layout MTD real) para `readMBR`; en este kernel solo existen mtd0-2, así
> que aborta antes de crear los servicios. Por eso no hay `parser`, ni `login`
> con consola, ni `novasock`/`logsocket`: nada de lo que viene detrás de ese
> punto llega a ejecutarse. El `mk` manual de H12 tampoco sirvió: `sstore` y
> `log` arrancan y quedan vivos, pero los sockets aparecen tarde o no aparecen
> (`storereg` sí salió, `novasock`/`logsocket` no) porque el supervisor real es
> `loader`, no esos binarios sueltos.
>
> **H13 (armada):** el init crea `ln -sf /dev/mtdblock0 /dev/mtdblock18` antes de
> `switch_root` — mtdblock0 es el mtdram RouterBoot que ya contiene el
> hard/soft config sintético (mismos bytes que la placa, sin tocar NAND). El
> `postdiag` vuelve a ser un volcado simple a los 150 s. Imagen
> `out/uImage-563-H13`; captura con `--post 300`.
>
> **H11 (arranque real, 11:44) — el router SÍ arranca servicios.** A los ~400 s:
> `/ram/storereg` existe (socket), `/nova/bin/sstore` (pid 1247) y `/nova/bin/mode`
> (pid 1408) corren, y `storereg` está en `/proc/net/unix`. Lanzar `sstore` a
> mano **crea `/ram/novasock`**; `/nova/bin/log` es el único binario que menciona
> `logsocket`. **Falta `/ram/logsocket`**, y el bucle auxiliar de `user` espera
> los tres sockets, así que `user` nunca arranca y `login` no tiene consola nova
> (`parser`) a la que conectarse → `MikroTik Login:` seguido de
> `SCRIPT ERROR: interrupted`.
>
> Importante: el kernel cambia `printk` a `logring0` (`printk: console [logring0]
> enabled`) y **no hay nodo `/dev/logring`**; por eso la consola serie sale
> desordenada/tardía y los `postdiag` anteriores veían estados viejos. `loader`
> a mano **no muere nunca**, simplemente espera (`loader` 1698 vivo a los 400 s).
>
> **H12 (armada):** a los 150 s completa la cadena `mk /ram/storereg sstore`,
> `mk /ram/novasock sstore`, `mk /ram/logsocket /nova/bin/log`, mata
> `login`/`parser` viejos, lanza `/nova/bin/loader`, espera 20 s y vuelca `ps`,
> `/ram`, `user.log`, `/proc/net/unix` y los `.diag`. Captura con `--post 300`.
> Imagen `out/uImage-563-H12`, MD5 en el registro.
>
> **H10:** Hallazgo clave de H10: el `postdiag` a 110 s cae **antes** de que
> `sysinit` llegue a `Starting services...`; a esa altura `/dev/logring` **no
> existe** (`ls: /dev/logring: No such file or directory`), así que los volcados
> a 45 s y 110 s siempre han retratado una fase previa al arranque de servicios.
> `loader` lanzado a mano a los 110 s **no muere** (sigue vivo 5 s, sin salida) y
> **no crea nada** (`novasock`, `storereg` y `logsocket` siguen missing; `/ram`
> solo tiene `jiffies`, `netns`, `pckg`, `run`, `shm`). Además `/nova/etc/services`
> es un **directorio** con `system.x3` (tabla binaria: telnet, ftp, www, www-ssl,
> api, api-ssl, winbox), no un fichero de texto.
>
> **H11 (armada, pendiente):** el `postdiag` ya no duerme 110 s fijos: espera a
> que exista `/dev/logring` (hasta 400 s), duerme 5 s y **entonces** vuelca ps,
> `/ram`, sockets, logring; después lanza `sstore` y luego `loader` a mano con
> salida a `/flash/rw/sstore.diag` y `loader2.diag`, y vuelve a mirar `/ram` y
> `logring`. Imagen `out/uImage-563-H11`; el cazador se arma con `--post 320`.

## 0. TL;DR (30 segundos)

- **Objetivo:** entrar en RouterOS 7.17 del ED500 por consola, WebFig o Winbox,
  ejecutar `/system license print`, `/system resource print` e `/interface print`,
  y que el sistema siga vivo.
- **Última imagen construida:** **H48**, `routeros-port/out/uImage-563`,
  **23.951.696 B**, MD5 `5f6a7e955f8215e09bdfb4eefc6a6fd1`, BUILD_RC=0,
  `ROS_POST=0`. Autorun con `/user set admin password="__ROSPASS__"`, sin
  `userseq.console`, H47 (red/bridge + telnetd antes de sysinit) y **H48:
  los cuatro scripts de defconf vaciados**.
- **Estado actual:** causa raiz del login **identificada**: `sysinit` ejecuta
  los scripts de defconf por RPC con timeout de 12 s; `get-custom-defconf`
  espera hasta 30 s a una interfaz `loopback` que aqui nunca aparece, el
  script se interrumpe y `sysinit` imprime `SCRIPT ERROR: interrupted`
  dejando la sesion de consola sin arrancar. No era autenticacion ni el
  reloj (H44/H46 ya lo descartaron). H48 quita defconf de la ecuacion.
- **Próximo paso:** arrancar H48 y comprobar que el error desaparece y que
  `admin` obtiene prompt `[admin@MikroTik] >`; si sale, ejecutar los tres
  `print`. Si sigue el `SCRIPT ERROR`, la siguiente prueba es `:delay`/jiffies
  dentro del motor de scripts (unico consumidor que queda).

## 1. Objetivo, hardware y restricciones

- **Placa:** Genexis Pure ED500, MIPS32 big-endian, RouterOS 7.17 (kernel 5.6.3).
- **Arranque:** U-Boot por TFTP a RAM. **No se escribe NAND/UBI.**
- **No tocar:** `license.key` (no versionada), identidad RouterBoot sintética
  (`ros/rb_hardconfig.bin`), lógica de licencia. Nada de bypass ni falsificación.
- **No subir a Git:** `license.key`, `out/`, `ros/`, `tools/winbox/`, tokens o
  contraseñas. Las credenciales de trabajo son las del autorun; no escribirlas
  en commits, issues ni logs.
- **Un solo cambio funcional por arranque.** H1 es solo el reloj de userspace;
  el `CONFIG_HZ` del kernel no se toca. H2 (EVA/FPU) y la red son cambios
  separados.
- **No declarar éxito sin evidencia de arranque en placa.** Un build correcto no
  demuestra que el login funcione.

## 2. Ubicaciones, credenciales y entorno

- **Workspace:** `C:\Users\BFR\Documents\GenexisLicenseWorkingNew`
- **Repo:** `C:\Users\BFR\Documents\GenexisLicenseWorkingNew\routeros-port`
- **Remoto:** `https://github.com/biielfont/genexis-routeros-port.git`, rama `main`.
- **Build (WSL):**
  ```bash
  wsl.exe -u root -d kali-linux-d -e bash -lc \
    'cd /mnt/c/Users/BFR/Documents/GenexisLicenseWorkingNew/routeros-port && bash build-563.sh'
  ```
  Kernel en `/opt/ros-port/linux-5.6.3`; initramfs en `/opt/ros-port/initramfs`;
  config original de MikroTik en `/opt/ros-port/mips.config`.
- **Placa:** `192.168.1.2`; U-Boot `192.168.1.1`; PC `192.168.1.161`.
  Serie **COM4 a 115200**.
- **Puertos:** 80 WebFig, 8080 diagnóstico y autorun, 8291 Winbox, 8728 API.
- **Credenciales:** usuario `admin`; contraseña = la que fija
  `/flash/autorun.scr` (el script `rosconsole.py` la usa por defecto). No
  escribirla en este archivo ni en logs/commits.
- **TFTP:** `catch_final.py` sirve `routeros-port/out`; imagen `uImage-563`.
- **PC con varias IPs:** para hacer ping a la placa hay que elegir la interfaz:
  ```bash
  ping -n 3 -S 192.168.1.161 192.168.1.2
  ```
  Sin `-S` Windows puede decir "Host de destino inaccesible".

## 3. Estado actual: H1

### 3.1 Qué se cambió (commit `2c4e83a`)

- `routeros-port/tools/tickfile.c`
  - `ROS_HZ 100` (antes 250), `NS_PER_TICK = 10 ms`.
  - `INITIAL_JIFFIES = -300 * ROS_HZ = -30000`.
  - `j = (uint32_t)(INITIAL_JIFFIES + elapsed)`; antes era
    `elapsed - INITIAL_JIFFIES` (signo invertido).
  - Así `libumsg::getJiffies()` (= `j + 30000`) empieza en **0** y avanza a
    **100 Hz**, que es lo que espera RouterOS.
- `routeros-port/init-initramfs.sh`
  - Mensajes `tickfile 100 Hz`.
  - `webdiag` añade: `ifconfig -a`, `brctl show`, `/proc/net/dev`, miembros
    `/sys/class/net/*/brif`, `dmesg` filtrado por `Oops|segfault|BadVA`, y dos
    muestras de `/ram/jiffies` + `/proc/uptime` con delta (esperado ≈100
    ticks/s; ≈200 ticks en la muestra de 2 s).
- `routeros-port/build-563.sh`
  - Guarda que aborta si `tools/tickfile.c` no tiene exactamente
    `#define ROS_HZ 100`.
- `CONFIG_HZ=250` del kernel **no se cambió** en H1. El desajuste es entre el
  kernel y el reloj que consume `libumsg`; H1 corrige el userspace.

### 3.2 Imagen y verificación

- `out/uImage-563`: **23.583.144 B**, MD5 **`1b33e4552b8609d7d3412c326e497b83`**
  (**H4**, autorun vacío).
- `out/uImage-563-H4`: copia exacta de H4, mismo MD5.
- `out/uImage-563-H3`: H3, 23.583.064 B, MD5
  `90dd5080cfed717cb07443c4115df7b3` (autorun sin `license import`).
- `out/uImage-563-tick100`: **H1**, 23.583.024 B, MD5
  `9e040a401557583fced0c117f0723398`.
- `logs/build-H1.log`: build completo, `BUILD_RC=0`, incluido en el commit.
- Initramfs empaquetado verificado:
  - `tickfile 100 Hz` y `jiffies rate` presentes en `/opt/ros-port/initramfs/init`.
  - `bin/tickfile`: 846.856 B, MD5 `3f4ed5f4ee69603902065a287474f339`.
- `CONFIG_HZ=250` confirmado en `/opt/ros-port/linux-5.6.3/.config` (intencional).
- Imagen anterior G (solo referencia): `out/uImage-563-diagG`, 23.581.976 B,
  MD5 `425f4125f06721047cea50cd1efa2cda`. Se construyó, pero no hay arranque G
  registrado (`logs/bootG.log` solo tiene la cabecera del cazador).

### 3.3 Git

- HEAD / `origin/main`: **`2c4e83a`** —
  `tickfile: emular reloj de 100 Hz para libumsg (H1)`.
- Base remota: `d936812` (`docs(routeros): correct login crash diagnosis`),
  encima de `f64b960`. El remoto solo aportó docs/comentarios; **no** cambió el
  código funcional de H1. El rebase fue limpio.
- `logs/try563_v2.log` aparece como modificado porque el cazador en vivo le
  añade la tanda H1. No revertirlo mientras el cazador esté corriendo.
- `routeros-port/AGENTS.md` pide commit + `push` a `origin/main` al terminar,
  con los logs relevantes. Este `AGENTS.md` de la raíz está **fuera** del repo;
  si se mueve dentro de `routeros-port`, hay que commitearlo también.

### 3.4 Cazador actual

- Proceso Python/TFTP: **PID 6636**, UDP `0.0.0.0:69`; shell padre **PID 12008**
  (relanzados el 25/11 a las 10:25 CET sirviendo **H4** con `--post 120`).
- Sirve `out/uImage-563` (23.583.024 B) y espera U-Boot **12 h** desde las
  09:24 CET del 25/11.
- `logs/bootH1.out` confirma:
  `U-Boot 192.168.1.1 -> TFTP en 192.168.1.161`, `TFTP escuchando en 0.0.0.0:69`,
  `imagen: uImage-563 (23583024 bytes)`, `esperando U-Boot...`.
- Al cazar U-Boot: fija `serverip`/`tftpdstp`, transfiere, comprueba tamaño y
  hace `bootm`. Libera COM4 45 s después de `bootm`.
- `catch_final.py` **no** lanza el login por sí solo. El 25/11 se relanzó
  encadenado en un único shell: al terminar `catch_final.py`, si la tanda nueva
  (`logs/bootH1c.log`) contiene `Bytes transferred`, espera 20 s y lanza
  `rosconsole.py` con `MSYS_NO_PATHCONV=1` y los tres `print`, hasta 3 intentos.
  Todo queda en `logs/autologin.log`. Si no hubo transferencia, no intenta login.
- El 25/11 se añadió `catch_final.py --post N`: segundos de consola tras
  `bootm` (por defecto 45). Con `--post 240` se captura el Oops tardío de
  `webdiag`/`ifconfig` (~95 s), principal sospechoso de que la placa muera antes
  de los ~135 s.
- **Los PIDs pueden haber cambiado** si esta sesión es posterior. Verificar antes
  de asumir:
  ```bash
  netstat -ano | grep -E ':69[[:space:]]'
  tasklist | grep -i python
  cat routeros-port/logs/bootH1.out
  ```
  Si el cazador ya no está y la placa sigue sin arrancar, relanzarlo (ver §5).

### 3.5 Qué está validado y qué no

- **Validado:** compilación, empaquetado del initramfs, guarda de `ROS_HZ`,
  MD5 de la imagen, TFTP escuchando, sintaxis de los scripts, commit/push.
- **Validado en placa (25/11):** H1 arranca (TFTP 23.583.024 B exactos,
  `bootm`, `Linux version 5.6.3 #192`), llega a `sysinit`/`Starting...`/`flash`,
  genera el autorun y **no hay `signal 11` ni Oops** en el arranque. Las
  credenciales `admin` + contraseña del autorun son aceptadas (no hay `Login failed`).
- **No validado:** prompt `[admin@MikroTik] >`, los tres `print`, WebFig/Winbox,
  delta de jiffies y `/flash/rw/user.log`. Tras los `SCRIPT ERROR` la consola
  quedó muda y sin ARP/HTTP: hace falta otro ciclo de corriente.
- **Ojo:** `/flash/rw` es volátil (`nand=no`), así que el autorun se regenera en
  cada arranque con el `license import` roto. No "se arregla solo".

## 4. Diagnóstico

### 4.0 Diagnóstico vigente (2026-11-26): el fallo está en la SESIÓN, no en el login

Secuencia real en placa, reproducible, con consola virgen y sin nadie más
escrito en `ttyS0`:

```
MikroTik  ()
MikroTik Login: admin        <- usuario escrito por nosotros
Password:                    <- contraseña escrita por nosotros
SCRIPT ERROR:  interrupted   <- siempre, dos espacios
```

Bytes exactos (capturados con `od -c` en `logs/try563_v2.log`): tras
`Password:  \r\n` viene `SCRIPT ERROR: ` + ` interrupted` + `\r\n\r\n` y **nada
más**; nunca aparecen los otros dos fragmentos de `sysinit`
(`error while running ` y ` script: `).

**Prueba decisiva (H46):** con el usuario **inexistente `zzz`** el resultado es
idéntico — `SCRIPT ERROR: interrupted`. Nunca sale
`Login failed, incorrect username or password`, aunque esa cadena existe en
`/nova/bin/login`. Por tanto:

1. **No es autenticación.** La validación de credenciales ni se alcanza o da
   igual su resultado; `admin` + contraseña del autorun no estaba fallando.
2. **El canal de mensajes de `login` funciona** (pinta `Login:`, `Password:`, y
   el eco del usuario), así que el serie y el modo terminal están bien.
3. **Lo que se cae es el arranque de la sesión**, es decir el script de consola
   que algo ejecuta al entregar el terminal. `sysinit` es el único binario que
   contiene el literal `SCRIPT ERROR: `, `interrupted` es el nombre de error de
   `parser` para **EINTR**, y `sysinit` también contiene las rutas
   `/ram/userseq.console` y los cuatro `autorun.scr`.
4. Un comando a ciegas (`/system resource print`) enviado justo después del
   error **no responde nunca**: la sesión no existe, no es un fallo de pintado.

Conclusión operativa: hay que averiguar **qué script intenta ejecutar** y por
qué recibe EINTR. Sospechoso número uno: `/ram/userseq.console` ("user sequence
console"), ruta que `login` referencia por GOT en VA `0x424910` (offset
`0x24910`), no por `lui/addiu`.

### 4.0.1 Qué se ha probado y DESCARTADO (2026-11-26)

- **Temporizadores rotos (hipótesis principal durante media sesión):
  DESCARTADA en placa.** `alarm(1)`, `setitimer(ITIMER_REAL)`, `timerfd` y
  `clock_nanosleep` funcionan: `poll` devuelve EINTR con `alarma=1` y
  `dt=1.004`; `timerfd set=0 poll=1 rev=0x1 dt=1.004`. Es decir, el kernel
  duerme y entrega señales correctamente. (Antes sí hubo un fallo real de
  reloj: faltaba `CONFIG_COMPAT_32BIT_TIME`, que hacía `ENOSYS` en `select`,
  `nanosleep`, `usleep` y `pselect6`; **eso sí se arregló** con
  `--enable COMPAT_32BIT_TIME` en `build-563.sh` y quedó verificado con
  `timediag`.)
- **`/ram/userseq.console` vacío creado por el init: DESCARTADO y contraindicado.**
  Con el fichero vacío el login aborta al instante, nada más pintar el banner
  (H28). El `postdiag` antiguo lo creaba, así que **todos** los arranques con
  `ROS_POST=1` se autosaboteaban. Con `ROS_POST=0` el fichero no se crea.
- **Que el problema fuera el autorun: DESCARTADO** (ya con autorun vacío salía
  el mismo error) y **que fuera la contraseña: DESCARTADO** (H46, usuario falso).
- **Que el volcado `postdiag` matara la sesión: DESCARTADO.** H45/H46 sin
  `postdiag` (consola totalmente virgen) dan el mismo `SCRIPT ERROR`.
- **Reinicio espontáneo de la placa (H43, `ROM VER: 2.1.0` tras el observador):
  no reproducido** en H44 con el mismo código de temporizadores. Puntual.
- **`signal 11` en `user`:** ya no aparece; el problema actual es anterior.
- **Bug propio corregido:** el cazador anunciaba el tamaño de la imagen al
  arrancar y, tras recompilar, el chequeo fallaba
  (`### TAMANO DISTINTO: 23949872 != 23949728 ###` x16, bucle de descargas sin
  `bootm`). Ahora **relee el tamaño en cada intento**.
- **Sincronización del login corregida:** el prompt `MikroTik Login:` sale a
  **up≈140 s**, no a los 45 s; `_login` espera hasta 190 s y lee 60 s tras la
  clave. Antes se intentaba demasiado pronto.
- **Volcados y login son mutuamente excluyentes:** cualquier escritura nuestra
  en `ttyS0` durante la sesión la mata. Para intentos de login hay que usar
  `ROS_POST=0` y no volcar nada.
- **Tras `SCRIPT ERROR` la consola deja de transmitir** a cualquier baud rate y
  no vuelve forzando RTS/DTR. También parece **bloquear** las escrituras
  posteriores desde otros procesos (el observador H41 nunca llegó a imprimir su
  segunda marca), así que no hay canal de post-mortem por el serie.

### 4.0.2 Red: por qué se pierde y qué cambia H47

En placa el switch **sí funciona**:

```
gswip-xrx500 1c000000.switch: probed GSWIP version 30 mod 0
gswip-xrx500 ... lan4: Link is Up - 1Gbps/Full - flow control rx/tx
IPv6: ADDRCONF(NETDEV_CHANGE): lan4: link becomes ready
bridge2: Unknown symbol switch_sched_mc_flood_update (err -2)
```

El puerto del PC (`lan4`) tiene enlace a 1 Gbps. El problema es **cuándo y
dónde** se pone la IP: `netup` arranca en segundo plano **tras** `sysinit`,
espera 60 s y crea `br0` con `lan1..lan4` — para entonces RouterOS ya tomó los
puertos DSA y `br0` se queda sin miembros ("br0 creado" repetido, 80/8080/8291
pasan a `000`). Además `bridge2.ko` no carga por símbolos que faltan
(`switch_sched_mc_flood_update`, `per_cpu_xmit_switched`).

**H47** mueve la red **antes** de `sysinit`, con los puertos aún libres:
`brctl addbr br0` + `lan1..lan4` + `192.168.1.2/24` + `busybox telnetd -p 23`.
Objetivo doble: (a) recuperar la vía de gestión, (b) tener **shell root por
red** para depurar `login`/`parser`/`userseq.console` en vivo con `ps`, `wchan`
y los logs delante, en vez de a ciegas con un ciclo de corriente por intento.
Si RouterOS se lleva `br0`, la alternativa es reservar `lan4` para Linux
(quitar su `ros-name` en el DTS) y poner la IP directa en `lan4` sin bridge.

### 4.0.3 H48: de donde sale exactamente `SCRIPT ERROR: interrupted`

Desensamblado de `/sbin/sysinit` (ELF32 MSB, `0x402060`+`.text`, PLT resuelta
con `tools/pltmap.py`):

- `0x408ea8` = `"SCRIPT ERROR: "`, `0x408eb8` = `"error while running "`,
  `0x408ed0` = `" script: "`. Solo se referencian en `0x40485c` y `0x404a00`,
  dentro de la misma funcion (`0x40461c`).
- Esa funcion construye un `nv::message` (`insert<u32_id>`,
  `insert<string_id>`, `insert<string_array_id>`) con la ruta del script y
  sus argumentos, y lo envia con `nv::getLooper()->sendMessage(msg, 12000)`
  (`0x4047c0: addiu $a3,$zero,0x2ee0`).
- Si la respuesta trae el flag de error, imprime `SCRIPT ERROR: <salida>` y
  luego `error while running <script> script: <salida>`. En placa solo sale
  la primera linea; la segunda no aparece nunca en
  `logs/try563_v2.log` (`grep -c "error while running"` = 0).
- **Los tres unicos llamantes** (`0x40868c`, `0x4086e8`, `0x408934`) pasan
  `"/nova/lib/defconf/defconf"`, `"customized default configuration"` +
  `"/nova/lib/defconf/get-custom-defconf"` y los de caps/wps-sync.

Es decir: el texto `interrupted` **no lo genera sysinit**, lo devuelve el
motor de scripts (`parser`, unico binario con la cadena `interrupted`);
 sysinit solo lo decora. Y el script que se interrumpe es, por descarte, uno
 de los de defconf: es el unico camino que lleva a ese `cout`.

Por que se interrumpe: `get-custom-defconf` empieza con

```
:local count 0;
:while ([:len [/interface find where type="loopback"]] = 0 && $count < 30) do={
    :set count ($count +1);
    :delay 1s;
}
```

y `defconf-caps`/`defconf-wps-sync` hacen lo mismo con `/interface ethernet
find`. En este port no hay interfaz `loopback` (y `net` tarda en publicar las
ethernet), asi que el script se va a 30 s mientras el RPC de sysinit solo
espera 12 s: sysinit lo interrumpe, el motor devuelve `interrupted`, y la
consola se queda a medias (el prompt sale, pero la sesion no llega a
arrancar). Eso explica el sintoma completo: mismo error con `admin` que con
`zzz`, comando ciego sin respuesta y consola muda despues.

**Arreglo H48:** en `init-initramfs.sh`, justo antes de `switch_root`, se
vacian (`: > f`) `/nova/lib/defconf/{defconf,get-custom-defconf,
defconf-caps,defconf-wps-sync}`. Un script vacio termina al instante, el RPC
responde sin error y sysinit sigue con la consola. La configuracion la sigue
poniendo el autorun (contrasena) y `netup` (red); defconf solo aplica la
configuracion de fabrica, que aqui no queremos.
### 4.1 H1: base de tiempo (la hipótesis que se está probando)

Evidencia:

1. El kernel compilado tiene `CONFIG_HZ=250`; el `mips.config` original de
   MikroTik (RouterOS 7.17) tiene `CONFIG_HZ=100`.
2. `libumsg::getJiffies()` lee `/dev/jiffies` y suma **30000 = 300 × 100**;
   está compilado para 100 Hz.
3. `tools/tickfile.c` avanzaba a 250 Hz y además calculaba
   `j = elapsed - INITIAL_JIFFIES` (signo invertido).
4. Medido en `logs/diag164.txt`: ~250 ticks/s.

Consecuencia: los timers de `login`, `www`, `user`, `parser` y `telser` caducan
2,5× antes; el timeout puede vencer antes de completar la sesión y el proceso
muere con `SIGSEGV` (`died with signal 11`). La página estática carga porque no
usa esos timers; WebFig, Winbox, telnet y consola fallan porque comparten
`libumsg`.

H1 corrige solo esto: reloj de 100 Hz y `getJiffies()` 0-based. **No** se ha
demostrado todavía en placa.

### 4.2 Segundo fallo: la IP de gestión desaparece

`netup` crea `br0` con `bridge2.ko` y le pone `192.168.1.2`. RouterOS
(`net`/`bridge2`) toma los puertos DSA y el `br0` se pierde; `netup.log` muestra
"br0 creado" repetido cada ~0,5 s. Por eso 80/8080/8291 pasan a `000` aunque los
procesos sigan vivos. Esto es **independiente de H1**.

El `webdiag` de H1 ahora registra `ifconfig -a`, `brctl show`, `/proc/net/dev` y
los miembros `brif` para confirmar dónde queda la IP. Si H1 hace que el login
funcione pero WebFig/Winbox no, el siguiente paso es la red: reservar `lan4`
para Linux (quitar su `ros-name` en `norrland.dts`), poner `192.168.1.2` directo
en `lan4` sin bridge y dejar `lan1..3` para RouterOS; o mover la IP al bridge de
RouterOS cuando aparezca.

### 4.3 H2: EVA/FPU (solo si H1 no basta)

Hay un Oops de kernel en `_save_fp_context` (`ifconfig`, PID 124,
`BadVA cd46300c`, `sw a1,12(a0)`) con `CONFIG_CPU_MIPS32_3_5_EVA=y`, opción que
**no** está en el `mips.config` original. Es un candidato a SIGSEGV distinto.

Confirmado el 25/11 en `/opt/ros-port/linux-5.6.3/.config` (líneas 266-267):
`CONFIG_CPU_MIPS32_3_5_FEATURES=y` y `CONFIG_CPU_MIPS32_3_5_EVA=y`; el
`/opt/ros-port/mips.config` original **no** define ninguna de las dos. La
discrepancia con MikroTik es real, no una sospecha.

Evidencia de timing del 25/11: en dos arranques la consola estaba viva a los
66 s y muda a los 135 s; en otro el login funcionó a los 137 s. Se sospechó de
`webdiag` (`ifconfig -a` a los ~95 s), pero **`--post 240` no mostró ningún
Oops ni `BadVA`**: la placa no muere por FPU en esa ventana. H2 queda en espera,
no descartado del todo.

Si H1 sigue con `signal 11`, el siguiente arranque debe desactivar **solo**
`CONFIG_CPU_MIPS32_3_5_EVA`/`3_5_FEATURES`/`VI`/`EI` (una variable) y revisar
`dmesg`. No mezclar H2 con H1 ni con la red.

### 4.4 Descartado o no demostrado

- **Duplicado de `/nova/bin/user`:** no demostrado. El remoto `d936812` corrigió
  ese diagnóstico y restauró `ROS_STARTUSER=1`; no atribuir el fallo al
  duplicado. La imagen H1 usa `ROS_STARTUSER=1`.
- **`ROS_REALLOGIN=1` / `login console`:** descartado; en D y E tumbó red y
  consola. Se mantiene `ROS_REALLOGIN=0`.
- **Licencia:** una licencia válida no elimina el cuelgue; la ruta de
  autenticación falla igual. El import del autorun es un tema aparte.
- **`flash.ko` manual:** cargarlo explícitamente bloquea el arranque; debe
  resolverlo `sysinit`/el kernel, no el initramfs.
- **`/ram/userseq.console` vacío:** crearlo antes de `sysinit` colgó el arranque;
  no crearlo.
- **`/system license import file-name="license.key"` en el autorun:** causa
  del `input does not match any value of file-name`. Retirado en **H3**; la
  licencia se importará a mano.
- **`/user set admin password` en el autorun:** con el servicio `user` aún sin
  arrancar (`user: espera a /ram/storereg`), el script se cuelga sobre la
  consola, imprime `SCRIPT ERROR: interrupted` y deja el `getty` sordo. Ese es
  el fallo que queda tras H3; **H4** deja el autorun vacío y la contraseña se
  fija a mano.

## 5. Cómo probar

### 5.1 Build

```bash
wsl.exe -u root -d kali-linux-d -e bash -lc \
  'cd /mnt/c/Users/BFR/Documents/GenexisLicenseWorkingNew/routeros-port && bash build-563.sh'
```

Comprobar al final: `BUILD_RC=0`, `out/uImage-563`, tamaño/MD5, y que
`tools/tickfile.c` siga con `#define ROS_HZ 100`.

### 5.2 Arranque y captura

El cazador actual ya está armado (ver §3.4). Si hay que relanzarlo:

```bash
cd routeros-port
export MSYS_NO_PATHCONV=1
off=$(stat -c %s logs/try563_v2.log 2>/dev/null || echo 0)
python -u catch_final.py --horas 12 > logs/bootH1.out 2>&1
# al terminar el cazador, extraer solo la tanda nueva:
tail -c +$((off+1)) logs/try563_v2.log | tr -d '\000' > logs/bootH1.log
```

`catch_final.py` sirve `out/uImage-563`, espera el prompt `grx500 #`, fija
`serverip`/`tftpdstp`, transfiere y hace `bootm`. Libera COM4 45 s después de
`bootm` salvo que se use `--seguir`.

### 5.3 Login y los tres print

Con COM4 libre (el cazador la libera solo):

```bash
cd routeros-port
export MSYS_NO_PATHCONV=1
python -u tools/rosconsole.py \
  --cmd '/system license print' \
  --cmd '/system resource print' \
  --cmd '/interface print'
```

- `MSYS_NO_PATHCONV=1` es **obligatorio** en Git Bash: sin él, `/system ...` se
  convierte en `C:/.../git/system ...` y los comandos llegan mal (pasó el 24/11
  a las 14:09).
- El script espera `Login:`, manda el usuario byte a byte, espera `Password:` y
  prueba la contraseña del autorun; si falla, reintenta con vacía.
- Si RouterOS pide cambiar la contraseña, usar `--nueva`.
- La consola completa queda en `logs/rosconsole.log`; el wrapper la extrae a
  `logs/loginH1.log`.

### 5.4 Si hay red

```bash
curl -sS --max-time 10 http://192.168.1.2:8080/diag.txt -o logs/diagH1.txt
ping -n 3 -S 192.168.1.161 192.168.1.2
```

El `diag.txt` lo reescribe `webdiag` cada ~5 s. Si la IP de gestión desapareció
por el `br0`, el HTTP no responderá aunque los procesos sigan vivos; la serie es
la fuente primaria.

## 6. Criterios de éxito/fracaso de H1

**Éxito (los tres primeros son obligatorios):**

- La consola llega a `[admin@MikroTik] >` tras `admin` + contraseña.
- No aparece `died with signal 11` en `user.log`/consola.
- `/flash/rw/user.log` no contiene `exit=139`.
- El delta de `jiffies`/`uptime` del `webdiag` es ≈100 ticks/s
  (≈200 ticks en la muestra de 2 s).
- No hay Oops nuevo en `dmesg` (`Oops`, `segfault`, `BadVA`).
- Entonces ejecutar y guardar los tres `print`.

**Fracaso / siguiente paso:**

- Si sigue `signal 11`: H2 (EVA/FPU), un solo cambio.
- Si el login funciona pero 80/8291/8728 no: problema de red/`br0`, arreglo
  separado.
- Si la placa queda muda: no hay conclusión; hace falta otro ciclo de
  alimentación y el cazador.

**Resultado real de H1 (25/11 09:27):** se cumplen "arranca sin `signal 11`" y
"credenciales aceptadas"; **no** se cumple "llega a `[admin@MikroTik] >`" porque
el autorun falla (`license import`) y la consola queda muda. No es fracaso del
reloj: el SIGSEGV ya no aparece. Es un fallo distinto, del autorun.

**Timing del login (25/11, dos arranques):**

- Arranque 1: a los ~66 s del `bootm` todavía no hab\u00eda `Login:`; a los ~137 s
  apareci\u00f3 y **`admin` + contraseña del autorun fue aceptado** (solo salieron los `SCRIPT ERROR`
  del autorun).
- Arranque 2: el intento a los ~66 s encontr\u00f3 el prompt de `Login:` pero el
  autorun a\u00fan no hab\u00eda aplicado la contrase\u00f1a; al meter la contraseña del autorun RouterOS
  volvi\u00f3 a `MikroTik Login:` (login rechazado, sin mensaje de error).
- Conclusi\u00f3n: no intentar login antes de ~120 s post-`bootm`; antes de eso el
  prompt existe pero la contrase\u00f1a a\u00fan no. El wrapper debe esperar y
  reintentar, y `rosconsole.py` debe limpiar el buffer antes de la clave para
  distinguir "vuelve a Login" (fallo) de `SCRIPT ERROR` (sesi\u00f3n abierta).

## 7. Registro de pruebas

| Fecha | Imagen | Cambio | Resultado | Evidencia |
|---|---|---|---|---|
| 23/11 13:45 | pre-H1 | login consola | FALLO: `died with signal 11` tras `admin` | `logs/rosconsole.log` |
| 23/11 15:58 | pre-H1 | login consola | FALLO: mismo `signal 11` | `logs/rosconsole.log` |
| 24/11 14:09 | pre-H1 | login consola | Llegó a `MikroTik Login: admin` + `Password:`, **no** a `[admin@…] >`; los `--cmd` se corrompieron por Git Bash | `logs/rosconsole.log` |
| 24/11 | #161 | licencia/autorun | Servicios y 80/8291/8728 llegan a abrir; el login/API cuelga; no es la licencia | `docs/HANDOFF-2026-11-24.md`, `logs/diag164.txt` |
| 24/11 | G `425f…` | diagnóstico | Construida; placa sin respuesta; sin boot G registrado | `logs/bootG.log` (solo cabecera) |
| 24/11 22:16 | H1 `9e04…` | tickfile 100 Hz | **PENDIENTE**: cazador armado; placa sorda; login no probado | `logs/bootH1.out` |
| 25/11 09:24 | H1 `9e04…` | rearme cazador + auto-login | **PENDIENTE**: cazador PID 8152 sirviendo H1; login encadenado; falta ciclo de corriente | `logs/bootH1c.out`, `logs/autologin.log` |
| 25/11 09:27 | H1 `9e04…` | arranque real + login | **AVANCE**: arranca sin `signal 11`; `admin` + contraseña del autorun aceptado; el autorun falla (`license import`) y la consola queda muda | `logs/bootH1c.log`, `logs/rosconsole.log` |
| 25/11 09:56 | H1 `9e04…` | captura 240 s | **SIN Oops de FPU**: la consola muere por el autorun, no por `webdiag`/EVA | `logs/bootH4b.log` |
| 25/11 10:05 | H3 `90dd…` | autorun sin `license import` | **PARCIAL**: desaparece `input does not match any value of file-name`; sigue `SCRIPT ERROR: interrupted` y la consola queda sorda (culpa del `/user set`) | `logs/bootH5a.out` |
| 25/11 10:25 | H4 `1b33…` | autorun VACÍO | **SIN CAMBIO**: con autorun vacío sigue `SCRIPT ERROR: interrupted` → no lo causa el autorun | `logs/bootH6a.out`, `logs/try563_v2.log` |
| 25/11 10:45 | H5b `124e…` | postdiag a 110 s + `/ram`, `user.log`, `loader.trace` | **DIAGNÓSTICO**: ni `storereg`, ni `novasock`, ni `logsocket`; `user.log` vacío; bucle de `user` aún esperando; banner `MikroTik  ()` con versión vacía | `logs/bootH9a.log` |
| 25/11 11:20 | H10 `e614…` | postdiag: hijos de sysinit + `/dev/logring` + `loader` manual | **DIAGNÓSTICO**: `/dev/logring` **no existe** a 110 s (llega en `Starting services...`); `loader` a mano **vive** pero no crea sockets ni escribe nada; `system.x3` es la tabla de daemons de red | `logs/bootH10a.out`, `logs/try563_v2.log` |
| 25/11 11:40 | H11 | postdiag espera a `/dev/logring` y prueba `sstore`/`loader` después de servicios | **DIAGNÓSTICO**: `/dev/logring` **nunca** existe (printk va a logring0); a 400 s `storereg` existe, `sstore`+`mode` corren; `sstore` a mano crea `novasock`; falta `logsocket` → `user` nunca arranca | `logs/bootH11a.out`, `logs/try563_v2.log` |
| 25/11 12:05 | H12 | completar cadena `storereg`→`novasock`→`logsocket` y lanzar `loader` a los 150 s | **CAUSA RAÍZ**: `loader`: `readMBR: could not open /dev/mtdblock18: 2` → `Failed to read MBR`; aborta antes de crear servicios | `logs/bootH12a.out`, `logs/build-H12.log` |
| 25/11 12:35 | H13 | `mtdblock18 -> mtdblock0` (RouterBoot RAM sintético) | **PENDIENTE**: construida y armada; falta ciclo de corriente | `logs/build-H13.log`, `logs/bootH13a.out` |
| 26/11 | H28 | `userseq.console` vacío antes de `sysinit` | **FALLO CONOCIDO**: el login aborta al instante nada más pintar el banner → **no crear** ese fichero | `logs/` (tanda H28) |
| 26/11 | H41 | observador post-login por `ttyS0` | **NO SIRVE**: arranca (`up=16`) pero nunca imprime la segunda marca; sospecha de escritura bloqueada en `ttyS0` tras morir la sesión | `logs/` (tanda H41) |
| 26/11 | H43 | reset con el mismo código de timers | **PUNTUAL**: `ROM VER: 2.1.0` una vez; no se reprodujo en H44 → no es del temporizador | `logs/try563_v2.log` |
| 26/11 | H44 | `timediag`: `alarm`/`setitimer`/`timerfd`/`clock_nanosleep` | **DESCARTADO**: kernel duerme y entrega señales bien (`poll`→EINTR, `alarma=1`, `dt=1.004`) | `logs/` (tanda H44) |
| 26/11 | H45 | consola **virgen**, `ROS_POST=0`, login esperando al prompt real (up≈140) | **FALLO**: `admin` + contraseña del autorun → `SCRIPT ERROR: interrupted`; sin nadie más en `ttyS0` | `logs/catch-h45.out` |
| 26/11 | H46 | usuario **inexistente** `zzz` + comando ciego | **DECISIVO**: mismo `SCRIPT ERROR: interrupted`, nunca `Login failed, incorrect username` → **no es autenticación**; el ciego no responde | `logs/catch-h46.out` |
| 26/11 | H47 | `br0`+`192.168.1.2`+`telnetd 23` **antes** de `sysinit` | **ARMADA** (23.950.632 B): pendiente de ciclo de corriente y de probar `telnet 192.168.1.2` | `logs/catch-h47.out` |
| 27/11 | H48 | defconf neutralizado (4 scripts a 0 B) antes de `switch_root` | **ARMADA** (23.951.696 B, MD5 `5f6a7e95…`): pendiente de ciclo de corriente; se espera que desaparezca `SCRIPT ERROR: interrupted` | `logs/build-H48.log` |

> La fila H1 no es un fallo: es una prueba **no ejecutada**. No cambiar
> "PENDIENTE" por "FUNCIONA" sin la consola y los `print`.

## 8. Gotchas

- **`MSYS_NO_PATHCONV=1`** antes de `rosconsole.py`; si no, los `/system ...`
  se convierten en rutas de Windows.
- **`ping -S 192.168.1.161`**: el PC tiene varias IPs; sin `-S` puede fallar.
- **COM4 la retiene el cazador.** `rosconsole.py` necesita que la libere (45 s
  después de `bootm`). No abrir otra consola a la vez.
- **`catch_final.py` escribe la serie en `logs/try563_v2.log`** (13 MB y
  creciendo). No leerlo entero; usar `tail -c` o el `logs/bootH1.log` extraído.
- **`webdiag` arranca a los ~95 s** y llama `ifconfig -a`; si eso dispara el Oops
  de FPU, es H2, no H1.
- **No crear `/ram/userseq.console`** vacío antes de `sysinit`: aborta el login
  al instante (H28).
- **No escribir en `ttyS0` mientras se intenta el login**: cualquier escritura
  nuestra mata la sesión. Volcados y login son excluyentes (`ROS_POST=0`).
- **El login debe hacerse dentro del cazador** (`catch_final.py --login`), con el
  puerto serie ya abierto, no reabriendo COM4.
- **No esperar el prompt antes de up≈140 s**: sale tras `Starting services...`;
  intentar antes da "fallo de contraseña" falso.
- `out/uImage-563` y `ros/rootfs.squashfs` (7.17, MD5
  `a942f0ed9493a5a604356ddc7d16f80a`) son la base; 7.10 en
  `ros/rootfs-7.10.squashfs`.
- **No cargar `flash.ko` a mano**; el arranque se queda antes de `Starting
  services`.
- **No hacer `git push --force`.** Si `origin/main` avanzó, `git fetch` y
  `git rebase origin/main`.
- **El log crudo de 13 MB no se commitea a ciegas.** Commitear `bootH1.log` /
  `loginH1.log` extraídos y relevantes.

## 9. Protocolo para el siguiente agente

1. Lee este archivo y `routeros-port/AGENTS.md`.
2. Comprueba git:
   ```bash
   cd routeros-port
   git status --short
   git log -1 --oneline
   ```
   No revertir `logs/try563_v2.log` si el cazador sigue vivo.
3. Comprueba placa/cazador:
   ```bash
   netstat -ano | grep -E ':69[[:space:]]'
   tasklist | grep -i python
   cat logs/bootH1.out
   ```
   No asumir que los PIDs 12508/10140 siguen.
4. Si la placa no ha arrancado: no reconstruyas ni declares nada; pide un ciclo
   de alimentación o espera. La placa solo revive con corriente.
5. Si arrancó: lee `logs/bootH1.log` y `logs/loginH1.log`, aplica los criterios
   de §6 y actualiza este archivo con el resultado real.
6. Si H1 funciona: ejecuta los tres `print`, guarda la salida y actualiza el
   estado a **FUNCIONA** con la evidencia.
7. Si H1 falla: anota la línea exacta (`signal 11`, `Oops`, puerto `000`) y
   prepara **H2** o el arreglo de red, un solo cambio.
8. Al terminar: actualiza "Última actualización", "Estado", "Imagen/MD5",
   "Cazador" y "Registro"; commit + push de `routeros-port` con los logs
   relevantes.
9. Nunca escribas NAND/UBI, `license.key`, `ros/`, `out/` ni credenciales.

## 10. Archivos clave

- `routeros-port/tools/tickfile.c`: reloj de userspace; H1 = 100 Hz,
  `INITIAL_JIFFIES=-30000`, signo correcto.
- `routeros-port/init-initramfs.sh`: initramfs, `/dev/flash`, licencia, autorun,
  `user`, `webdiag`.
- `routeros-port/build-563.sh`: kernel + initramfs + guarda `ROS_HZ 100`.
- `routeros-port/catch_final.py`: TFTP + captura + `bootm`.
- `routeros-port/tools/rosconsole.py`: login serie byte a byte y comandos.
- `routeros-port/out/uImage-563`: H1 que sirve el cazador.
- `routeros-port/logs/build-H1.log`: build H1 (versionado).
- `routeros-port/logs/bootH1c.out`: stdout del cazador actual (25/11).
- `routeros-port/logs/autologin.log`: resultado del login automático encadenado.
- `routeros-port/logs/try563_v2.log`: serie cruda; crece ~15 MB por sesión.
- `routeros-port/logs/catch-h45.out`, `catch-h46.out`, `catch-h47.out`: cazador
  de los intentos limpios H45/H46 y del arranque con red H47.
- `routeros-port/tools/bootm_now.py`: hace `bootm 0x80500000` con lo ya cargado
  en RAM y sigue la sesión, sin ciclo de corriente.
- `routeros-port/tools/timediag.c`: prueba `alarm`, `setitimer`, `timerfd` y
  `clock_nanosleep`; escribe sin buffer directo a `/dev/ttyS0`.
- `routeros-port/tools/patch-h41.py`: sustituye el `postdiag` por el observador
  H41 (sin tocar `userseq.console`).
- `routeros-port/init-initramfs.sh`: además de lo anterior, `ROS_POST=0`,
  `ROS_TTYSHELL=0`, `rm -f $R/ram/userseq.console` y **H47** (red + telnetd
  antes de `sysinit`).
- `routeros-port/build-563.sh`: `--enable COMPAT_32BIT_TIME` y compila
  `timediag`.
- `routeros-port/catch_final.py`: TFTP + captura + `bootm`; `--login` (login con
  el puerto ya abierto, espera 190 s al prompt y lee 60 s), `--post`,
  `--user` (H46), `--ciego`, y relee el tamaño de la imagen en cada intento.
- `routeros-port/logs/rosconsole.log`: consola; contiene `Password:` y
  `signal 11` de intentos previos.
- `routeros-port/logs/diag164.txt`: diagnóstico con jiffies ~250/s.
- `routeros-port/docs/HANDOFF-2026-11-24.md`: handoff histórico (#161). Está
  desactualizado respecto a H1; este `AGENTS.md` manda para el estado actual.

- `routeros-port/tools/xref.py`: busca cadenas en un ELF MIPS y desensambla
  alrededor de sus referencias (usa `mipsdis.py`).
- `routeros-port/tools/pltmap.py`: resuelve la PLT (`lui $t7,hi; lw
  $t9,imm($t7)`) de un binario de RouterOS y anota cada `jal` con el nombre
  del simbolo; con esto se leyo el flujo de `sysinit` que imprime
  `SCRIPT ERROR: `.
## 11. Instrucciones del repo

`routeros-port/AGENTS.md`:

> Al terminar cada conversación, hacer commit de los cambios y `push` a
> `origin/main`, incluyendo los logs relevantes.

**Ubicación:** este documento es ahora `routeros-port/AGENTS.md`, dentro del repo
y versionado. El `AGENTS.md` de la raíz del workspace es solo un puntero a él,
para que no haya dos estados distintos. Los `logs/` crudos (`try563_v2.log`,
`rosconsole.log`) ya **no** se versionan: `logs/` está en `.gitignore` y esos
dos ficheros contienen la contraseña en claro; se destrackearon en el commit del
2026-11-26.

---

### Historial de este documento

- **2026-11-24 22:16 CET:** creado. H1 construida, commit `2c4e83a` subido,
  cazador armado, placa sorda; login H1 **pendiente de validación**.
- **2026-11-26:** reescrito el estado con la sesión H14…H47. Se documenta la
  prueba decisiva H46 (usuario falso → mismo error, luego **no es
  autenticación**), lo descartado (temporizadores, `userseq.console` vacío,
  autorun, contraseña, `postdiag` como asesino de la sesión), y lo añadido
  (H47 con red y telnetd antes de `sysinit` para depurar en vivo).
