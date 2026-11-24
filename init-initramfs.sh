#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

# 0 = arrancar /sbin/sysinit (el arranque real de RouterOS).
# 1 = shell de inspeccion, para mirar interfaces/modulos sin reiniciar.
# Se puede pedir el shell con ros.shell=1 en los bootargs.
ROS_SHELL=0
# sstore real de sysinit (sin stub) + user esperando el store.
ROS_POST=0
ROS_TTYSHELL=0
ROS_LOGINWRAP=0
# Let sysinit start the real sstore with its normal arguments. /dev/jiffies
# is backed before switch_root, so its mmap has valid storage.
ROS_STARTSTORE=0
# user se crea a demanda por loader cuando llega la peticion de login.
ROS_STARTUSER=1
ROS_REALLOGIN=0
ROS_PANICDUMP=0
case " $(cat /proc/cmdline 2>/dev/null) " in
	*" ros.shell=0 "*) ROS_SHELL=0 ;;
	*" ros.shell=1 "*) ROS_SHELL=1 ;;
	*" ros.post=0 "*) ROS_POST=0 ;;
esac

mount -t proc     proc     /proc
mount -t sysfs    sysfs    /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null
[ -c /dev/console ] || mknod /dev/console c 5 1 2>/dev/null

# --- RouterOS: si el squashfs va en el initramfs, arrancarlo ---
# El rootfs sale del npk oficial mipsbe (mismo 5.6.3 y mismo vermagic que
# este kernel). Se monta por loop y se cede el testigo a /sbin/sysinit.
if [ -f /ros.squashfs ]; then
	echo "--- RouterOS: montando rootfs ---"
	# RouterOS escribe en / y en /flash/rw (config, logs, ident). El squashfs
	# es de solo lectura, asi que va debajo de un overlay con tmpfs encima.
	mkdir -p /newroot
	if mount -t tmpfs tmpfs /newroot 2>/dev/null \
	   && mkdir -p /newroot/rom /newroot/upper /newroot/work /newroot/merged \
	   && losetup /dev/loop0 /ros.squashfs 2>/dev/null \
	   && mount -t squashfs -o ro /dev/loop0 /newroot/rom 2>/dev/null \
	   && mount -t overlay overlay \
		-o lowerdir=/newroot/rom,upperdir=/newroot/upper,workdir=/newroot/work \
		/newroot/merged 2>/dev/null; then
		echo "  overlay listo, arrancando /sbin/sysinit"
		R=/newroot/merged
		# Contrasena inicial de admin. Se puede cambiar sin recompilar con
		# ros.pass=... en los bootargs de U-Boot. El valor por defecto es
		# el del laboratorio y queda documentado; no es un secreto.
		ROSPASS=ed500
		for a in $(cat /proc/cmdline 2>/dev/null); do
			case "$a" in ros.pass=*) ROSPASS=${a#ros.pass=} ;; esac
		done
		mount -t proc   proc   $R/proc
		mount -t sysfs  sysfs  $R/sys
		mount -t devtmpfs devtmpfs $R/dev 2>/dev/null
		mkdir -p $R/dev/pts $R/dev/shm $R/ram $R/rw $R/flash/rw $R/tmp
		# ROSMode::save() abre /dev/jiffies en O_WRONLY y hace pwrite() de 88
		# bytes; si el nodo no existe, save() falla y el loader lo registra
		# como "ERROR: ROSMode::save failed". Un fichero normal en devtmpfs
		# basta y es volatil: no toca NAND ni licencia.
		: > $R/dev/jiffies 2>/dev/null || true
		# flash.ko registra el misc 10:248. Si el nodo no existe cuando
		# sstore arranca, se queda esperando el store. Se crea el char
		# (no un fichero regular: este dispara Demo license expired).
		[ -e $R/dev/flash ] || mknod $R/dev/flash c 10 248 2>/dev/null || true
		chmod 600 $R/dev/flash 2>/dev/null || true
		mount -t devpts devpts $R/dev/pts 2>/dev/null
		mount -t tmpfs  tmpfs  $R/ram 2>/dev/null
		mount -t tmpfs  tmpfs  $R/tmp 2>/dev/null

		# Adjunta UBI antes de montar /flash/rw. En un arranque desde
		# NAND el bootargs de U-Boot es ubi.mtd=ubi,0,30 y este kernel
		# (BCH-4 por pasos de 512 B) espera el VID header en 512; la UBI
		# stock lo tiene en 2048. Se adjunta a mano y, si el kernel ya
		# creo ubi0 sin rootfs_0, se vuelve a adjuntar con -O 2048.
		ubi_attach_ed500() {
			MTDNUM=$(sed -n 's/^\(mtd[0-9][0-9]*\):.*"ubi"$/\1/p' /proc/mtd 2>/dev/null | head -1 | sed 's/mtd//')
			[ -n "$MTDNUM" ] || MTDNUM=1
			if [ -e /dev/ubi0 ]; then
				HAVE_ROOTFS=0
				for d in /sys/class/ubi/ubi0_*; do
					[ -r "$d/name" ] || continue
					case "$(cat "$d/name")" in rootfs_*) HAVE_ROOTFS=1 ;; esac
				done
				if [ "$HAVE_ROOTFS" = 0 ]; then
					/bin/busybox ubidetach -d 0 2>/dev/null || true
				fi
			fi
			if [ ! -e /dev/ubi0 ]; then
				/bin/busybox ubiattach -m "$MTDNUM" -d 0 -O 2048 /dev/ubi_ctrl 2>&1 | sed 's/^/  /'
				[ -e /dev/ubi0 ] || ubiattach -m "$MTDNUM" -d 0 -O 2048 2>&1 | sed 's/^/  /'
			fi
		}
		ubi_attach_ed500

		# /flash volatil: diskd intenta mount("none","/flash",NULL,...) y
		# el kernel rechaza el fstype nulo; con este tmpfs /flash queda
		# montado y writable antes de sysinit.
		mount -t tmpfs  tmpfs  $R/flash 2>/dev/null
		mkdir -p $R/flash/rw
		# Persistencia: si rootfs_0 (el volumen que instala el .y3) esta
		# en NAND, /flash/rw vive ahi y la config/logs de RouterOS
		# sobreviven al reinicio. Si no, se queda en tmpfs como antes.
		mkdir -p $R/nand
		# Instalacion de un solo banco: run update_image escribe rootfs_0
		# y fija root_vol=rootfs_0. No se sigue root= del cmdline para no
		# acabar montando el banco stock si U-Boot hiciera un fallback.
		ROOTVOL=rootfs_0
		# La rootfs_0 actual de esta placa es la stock de Genexis, no la
		# RouterOS del .y3. Montarla como /flash/rw mezcla su /rw con el
		# userland de RouterOS y el login se queda colgado. Hasta flashear
		# el .y3, /flash/rw va en tmpfs (volatil).
		NAND_PERSIST=0
		if [ "$NAND_PERSIST" = 1 ] && mount -t ubifs -o rw "ubi0:$ROOTVOL" $R/nand 2>/tmp/nand.err; then
			echo "  NAND: $ROOTVOL montado rw en $R/nand"
			mkdir -p $R/nand/rw/tmp $R/nand/rw/logs $R/nand/rw/store \
				$R/nand/rw/cm $R/nand/rw/pckg $R/nand/rw/vstore
			rm -f $R/nand/pad $R/nand/log.sock 2>/dev/null
			rmdir $R/flash/rw 2>/dev/null
			# Enlace relativo: el init accede a $R/flash/rw ANTES de
			# switch_root. Un destino absoluto (/nand/rw) se resolveria
			# contra el initramfs, no contra $R, y dejaria /flash/rw
			# colgando hasta el switch_root.
			ln -s ../nand/rw $R/flash/rw
		else
			echo "  NAND: persistencia desactivada (rootfs_0 stock); /flash/rw en tmpfs"
			mount -t tmpfs  tmpfs  $R/flash/rw 2>/dev/null
		fi
		# /tmp y /rw son enlaces a /flash/rw/tmp y /flash/rw. El tmpfs de
		# /flash/rw se monta despues de crear los enlaces, asi que hay que
		# crear el destino ya con el tmpfs puesto o /tmp queda colgando y
		# login/devlog no pueden abrir sus sockets.
		# /var/run apunta a /rw/run; sin este destino sysinit registra
		# "broken path" y los servicios no pueden publicar sus sockets.
		mkdir -p $R/ram/run $R/ram/shm $R/ram/netns/main \
			$R/flash/rw/tmp $R/flash/rw/logs $R/flash/rw/store \
			$R/flash/rw/run $R/flash/rw/cm $R/flash/rw/pckg \
			$R/flash/rw/vstore 2>/dev/null || true
		# /dude es un enlace del rootfs a esta ruta; puede estar ausente en
		# builds sin el paquete, pero no debe quedar como enlace colgante.
		mkdir -p $R/flash/dude 2>/dev/null || true
		# En un RouterBOARD real /flash es una copia writable del rootfs.
		# sysinit espera /flash/nova, /flash/etc y /flash/home; sin ellos
		# los servicios fallan con "broken path". La copia es volatil.
		for d in nova etc home; do
			if [ -d "$R/$d" ]; then
				cp -a "$R/$d" "$R/flash/$d" 2>/dev/null && echo "  /flash/$d: copiado"
			fi
		done
		# /dev/jiffies: libumsg lo mmap-ea y lee un uint32 para calcular
		# todos sus timeouts. El modulo jiffies.ko del rootfs mapea la
		# pagina con un PFN incorrecto y provoca Bus error; por eso no se
		# usa. En su lugar hay un fichero regular de 8 KiB en /ram y el
		# helper tickfile escribe jiffies a 250 Hz (CONFIG_HZ=250).
		rm -f $R/dev/jiffies 2>/dev/null || true
		/bin/busybox dd if=/dev/zero of=$R/ram/jiffies bs=4096 count=2 2>/dev/null || true
		/bin/busybox ln -s /ram/jiffies $R/dev/jiffies 2>/dev/null || true
		cp /bin/tickfile $R/bin/tickfile 2>/dev/null || true
		chmod 755 $R/bin/tickfile 2>/dev/null || true
		if [ -x $R/bin/tickfile ]; then
			chroot $R /bin/tickfile >/dev/null 2>&1 &
			echo "  jiffies: tickfile 250 Hz sobre /ram/jiffies (8 KiB)"
		else
			echo "  jiffies: AVISO, falta /bin/tickfile"
		fi
		# loader lee un MBR y el ID de /dev/mtdblock71 antes de arrancar
		# los servicios. En este kernel no existe ese nodo; el loader
		# parcheado no exige el ID, pero si el fichero para readMBR.
		$R/bin/busybox dd if=/dev/zero of=$R/dev/mtdblock71 bs=512 count=1 2>/dev/null || true
		# No crear /ram/userseq.console vacio: sysinit/loader se cuelgan
		# antes de arrancar los servicios. Parser lo crea cuando hace falta.
		rm -f $R/ram/userseq.console 2>/dev/null || true
		# /rw es un enlace a /flash/rw en el rootfs. sysinit y /nova
		# esperan logs/store; sin ellos el logger falla con broken path.
		# /pckg es un enlace a /ram/pckg; /rw a /flash/rw. Hay que crear
		# los destinos, no el enlace, o mkdir falla y set -e mata al init.
		mkdir -p $R/ram/pckg/branding/rw $R/flash/pckg/branding/rw \
			$R/flash/rw/tmp $R/flash/rw/logs $R/flash/rw/store 2>/dev/null || true
		: > $R/ram/pckg/branding/rw/autorun.scr 2>/dev/null || true
		: > $R/flash/pckg/branding/rw/autorun.scr 2>/dev/null || true
		# Autorun de RouterOS: se ejecuta en el arranque de sysinit. Deja la
		# red usable sin consola (bridge, IP, DHCP) y fija la contrasena de
		# admin. Si bridge2 no carga, las ordenes fallan pero el fallback de
		# netup crea un bridge Linux; por eso el autorun no es la unica red.
		if [ -e $R/flash/rw/autorun.scr ]; then
			# Ya hay un autorun persistente en NAND: se respeta tal
			# cual. La contrasena solo se fija en el primer arranque;
			# el bootok borra esa linea despues para no pisar cambios.
			cp $R/flash/rw/autorun.scr $R/flash/autorun.scr 2>/dev/null || true
			echo "  autorun: usando el persistente de /flash/rw"
		else
			cat > $R/flash/autorun.scr <<'AUTORUN'
# ED500: configuracion inicial minima (solo primer arranque).
# RouterOS compila el script entero; una sola linea invalida impide que
# se ejecute cualquier orden. Solo se fija la contrasena; www ya viene
# habilitado en el rootfs. Nada de /delay: el login no debe interrumpirlo.
/user set admin password="__ROSPASS__"

AUTORUN
			sed -i "s/__ROSPASS__/$ROSPASS/" $R/flash/autorun.scr 2>/dev/null || true
			cp $R/flash/autorun.scr $R/flash/rw/autorun.scr 2>/dev/null || true
			cp $R/flash/autorun.scr $R/flash/rw/store/autorun.scr 2>/dev/null || true
			echo "  autorun: generado (primer arranque)"
		fi
		# sysinit consulta varias rutas de autorun; se copia el mismo
		# script a las copias volatiles para no depender del orden.
		for f in $R/ram/pckg/branding/rw/autorun.scr \
		         $R/flash/pckg/branding/rw/autorun.scr; do
			cp $R/flash/autorun.scr "$f" 2>/dev/null || true
		done
		# postlog es el script de logging que sysinit busca en /flash;
		# sin el, el motor de scripts da broken path.
		: > $R/flash/postlog 2>/dev/null || true
		# sysinit busca /flash/boot/VERSION, /flash/boot y lost+found.
		# Son rutas de arranque, no de licencia.
		mkdir -p $R/flash/boot $R/flash/lost+found $R/flash/var/pdb 2>/dev/null || true
		echo "7.17" > $R/flash/boot/VERSION 2>/dev/null || true
		# Stubs de scripts/estado que sysinit busca en /flash. El de
		# SHOW_LICENSE es solo el display; la licencia ya la valida el
		# sistema con la identidad RouterBoot y no se modifica.
		: > $R/flash/DFSTEST 2>/dev/null || true
		: > $R/flash/RESET 2>/dev/null || true
		: > $R/flash/SHOW_LICENSE 2>/dev/null || true
					# No truncar el estado persistente en NAND: si ya existe, se
			# conserva entre reinicios. En tmpfs da igual, pero con rootfs_0
			# en NAND estos ficheros son la configuracion de RouterOS.
			echo "  /flash/rw -> $(readlink $R/flash/rw 2>/dev/null) (nand=$( [ -d $R/nand/rw ] && echo si || echo no))"
			[ -e $R/flash/rw/rnd_seed ] || : > $R/flash/rw/rnd_seed 2>/dev/null || true
			[ -e $R/flash/rw/rosmode.msg ] || : > $R/flash/rw/rosmode.msg 2>/dev/null || true
			[ -e $R/flash/rw/startcount ] || echo 0 > $R/flash/rw/startcount 2>/dev/null || true
			echo "  /flash/rw: estado persistente comprobado"
		# Dirs de servicios que sysinit comprueba. No se crean los
		# marcadores UPGRADED/PCKGS_CHANGED/BRANDING_INSTALLED ni bbup:
		# vacíos hacen que sysinit reanude una instalación y falle con
		# "Resuming upgrade... ERROR: router installation failed".
		mkdir -p $R/flash/nova/lib/wireless $R/flash/rw/tmp/restoreBackup 2>/dev/null || true
		: > $R/flash/nova/etc/url 2>/dev/null || true
		: > $R/flash/logo.bmp 2>/dev/null || true
		: > $R/flash/boot/logo.bmp 2>/dev/null || true
		echo "  /flash: dirs, scripts y estado listos"
		ls -la $R/flash 2>/dev/null | sed 's/^/  /'
		FLASHMOUNT=$(mount | grep "on $R/flash type" | head -1)
		echo "  /flash: ${FLASHMOUNT:-NO-MONTADO}"
		if echo ok > $R/flash/.mount-test 2>/dev/null; then
			echo "  /flash: escritura OK"
		else
			echo "  /flash: escritura FALLO"
		fi
		# No crear /dev/flash a mano: flash.ko lo registra como misc
		# (char device) y un symlink previo a /dev/mtdblock0 impide que
		# devtmpfs cree el nodo correcto. mtdblock0 es el MTD RAM
		# RouterBoot, no el /dev/flash que espera RouterOS.
		echo "--- MTD del kernel ---"
		if [ -r /proc/mtd ]; then sed 's/^/  /' /proc/mtd; else echo "  sin /proc/mtd"; fi
		ls -l /dev/mtd* /dev/mtdblock* /dev/flash 2>&1 | sed 's/^/  /'
		# flash.ko lee la identidad RouterBoot (product ID, MAC, serial)
		# del bloque "Hard" del MTD RouterBoot. El mtdram arranca en
		# 0xFF: sin este bloque, hard_size=0xFFFFFFFF y vmalloc falla.
		# Es una identidad sintetica y volatil; no toca la NAND ni la
		# licencia.
		if [ -f /rb_hardconfig.bin ] && [ -e /dev/mtdblock0 ]; then
			echo "--- RouterBoot: hard config sintetico en el MTD RAM ---"
			if dd if=/rb_hardconfig.bin of=/dev/mtdblock0 bs=4096 conv=notrunc 2>/tmp/rbcfg.err; then
				echo "  escrito: $(wc -c < /rb_hardconfig.bin) bytes"
				MH=$(dd if=/dev/mtdblock0 bs=1 skip=4096 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')
				MS=$(dd if=/dev/mtdblock0 bs=1 skip=32768 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')
				echo "  magics: hard=$MH soft=$MS"
			else
				echo "  fallo: $(cat /tmp/rbcfg.err 2>/dev/null)"
			fi
		fi
		# flash.ko lo carga sysinit despues de este punto; no forzarlo
		# aqui para no bloquear el arranque antes de UBI/loader.
		echo "--- UBI ---"
		ubi_attach_ed500
		ls -l /dev/ubi* 2>&1 | sed 's/^/  /'
		for d in /sys/class/ubi/ubi0_*; do
			[ -r "$d/name" ] || continue
			echo "  $(basename "$d"): $(cat "$d/name")"
		done
		# rootfs_0 es el unico volumen del sistema. rootfs_1 no se
		# monta ni se usa: si existe, es la copia stock para recuperar
		# manualmente desde U-Boot, no un segundo banco de arranque.
		if mount | grep -q "on $R/nand type ubifs"; then
			echo "  UBI: rootfs_0 montado rw en $R/nand (persistencia)"
		else
			echo "  UBI: rootfs_0 no esta montado rw"
		fi
		# RouterOS calcula la validez de su licencia demo con el reloj del
		# sistema. El GRX350 arranca sin RTC util y el kernel cae en 2010,
		# con lo que RouterOS dice "Demo license expired!" y se para. Se
		# fija una fecha moderna antes de cederle el control.
		date -s "2026-11-19 12:00:00" >/dev/null 2>&1
		hwclock -w >/dev/null 2>&1
		echo "  fecha: $(date)"
		# El bootargs de NAND no trae panic=20; si el kernel hace panic,
		# que reinicie solo. El flag de arranque del U-Boot se queda como
		# este; no hay un segundo banco activo.
		echo 20 > /proc/sys/kernel/panic 2>/dev/null || true
		# RouterOS abre la consola por el nombre generico ttyS*; en este
		# SoC el puerto es el ASC de Lantiq (ttyLTQ0).
		for n in 0 1 2 3; do
			[ -e $R/dev/ttyS$n ] || ln -sf ttyLTQ0 $R/dev/ttyS$n 2>/dev/null
		done
		# Los modulos de red los carga sysinit en su orden. No se hace
		# insmod aqui: packet_hook.ko engancha el datapath y, si se carga
		# antes de que RouterOS este listo, puede dejar sin red al propio
		# initramfs. Solo se lista lo que hay.
		echo "--- modulos de red de RouterOS (los carga sysinit) ---"
		for m in drivers/net/packet_hook.ko drivers/net/phy_helper.ko \
		         drivers/net/switch.ko net/bridge/bridge2.ko; do
			f=$R/lib/modules/5.6.3/$m
			if [ -f "$f" ]; then
				echo "  $m: $(wc -c < "$f") bytes"
			else
				echo "  $m: no existe"
			fi
		done
		# RouterOS usa /dev/log antes de que su propio log service cree el
		# socket. En este devtmpfs un bind() no deja el nodo visible, asi
		# que el socket real vive en /flash/rw (tmpfs) y /dev/log es un
		# enlace. El logger minimo lo mantiene y vuelca a messages.
		cp /bin/devlog $R/bin/devlog 2>/dev/null || true
		chmod 755 $R/bin/devlog 2>/dev/null || true
		# El socket vive en /tmp (tmpfs): UBIFS no tiene por que soportar
		# sockets y un bind() sobre un socket viejo falla. Los mensajes
		# siguen yendo a /flash/rw/logs/messages (NAND si esta montado).
		rm -f $R/dev/log $R/flash/rw/log.sock $R/tmp/log.sock
		ln -s /tmp/log.sock $R/dev/log 2>/dev/null || true
		chroot $R /bin/devlog /tmp/log.sock 2>/dev/console &
		sleep 1
		ls -l $R/dev/log $R/tmp/log.sock 2>&1 | sed 's/^/  devlog: /'
		# Modo inspeccion: arrancar un shell dentro del rootfs de
		# RouterOS (trae bash) para ver estado, interfaces y licencia
		# sin necesidad de reiniciar a ciegas.
		# El bash de RouterOS vive en /pckg/option, que solo existe cuando
		# sus paquetes estan montados; en el rootfs base no esta. Se copia
		# el busybox estatico del initramfs al overlay y se arranca ese,
		# con / como root de RouterOS.
		if [ "$ROS_SHELL" = 1 ]; then
			# Tiene que llamarse "busybox": el binario elige el applet por
			# el nombre con el que se invoca; con otro nombre responde
			# "applet not found".
			cp /bin/busybox $R/bin/busybox 2>/dev/null
			chmod 755 $R/bin/busybox 2>/dev/null
			cp /bin/sysopen $R/bin/sysopen 2>/dev/null
			chmod 755 $R/bin/sysopen 2>/dev/null
			if [ -x $R/bin/busybox ]; then
				echo "--- shell dentro de RouterOS ---"
				# chroot y no switch_root: si el shell sale, el init sigue
				# vivo (con switch_root, salir del shell mata al PID 1 y el
				# kernel hace panic). La consola se abre a mano porque el
				# stdin del init no siempre llega al proceso.
				chroot $R /bin/busybox sh -i \
					0</dev/console 1>/dev/console 2>&1
				echo "  shell terminado, sigue el arranque normal"
			else
				echo "  no he podido copiar busybox, sigo con sysinit"
			fi
		fi
		# Red de gestion tras sysinit: sysinit deja cbm0/lan* abajo y sin
		# IP. Un ayudante volatil (busybox copiado al overlay) las levanta
		# cuando RouterOS ya ha arrancado, para poder validar web/API sin
		# depender de un shell en la consola. No toca NAND.
		cp /bin/busybox $R/bin/busybox 2>/dev/null || true
		chmod 755 $R/bin/busybox 2>/dev/null || true
		cat > $R/bin/netup <<'NETUP'
#!/bin/sh
# Red de gestion de ultimo recurso. No toca la NAND ni la config de RouterOS.
# - si RouterOS ya creo un bridge con IP, no hace nada;
# - si hay bridge sin IP, le pone 192.168.1.2;
# - si no hay bridge, crea br0 con ether1..4 o lan1..4, IP y DHCP.
# - mgmt.vlan=NN en los bootargs crea br0.NN y pone la IP ahi.
B=/bin/busybox
LOG=/flash/rw/netup.log
IP=192.168.1.2
MASK=255.255.255.0
VLAN=""
for a in $($B cat /proc/cmdline 2>/dev/null); do
	case "$a" in mgmt.vlan=*) VLAN=${a#mgmt.vlan=} ;; esac
done
log() { echo "$($B date '+%H:%M:%S' 2>/dev/null) $*" >> "$LOG"; }
$B sleep 5
i=0
while [ "$i" -lt 30 ]; do
	$B ifconfig cbm0 up 2>/dev/null
	for n in ether1 ether2 ether3 ether4 lan1 lan2 lan3 lan4; do
		$B ifconfig "$n" up 2>/dev/null
	done

	# Bridge creado por RouterOS (bridge, bridge1, ...).
	BR=""
	for d in /sys/class/net/*; do
		[ -d "$d/bridge" ] || continue
		n=${d##*/}
		# br0 es el bridge del fallback, no uno de RouterOS; si se cuela,
		# el script se cree que RouterOS ya tiene red y no configura la VLAN.
		[ "$n" = "br0" ] && continue
		BR=$n
	done
	if [ -n "$BR" ]; then
		if $B ifconfig "$BR" 2>/dev/null | $B grep -q 'inet addr'; then
			log "RouterOS ya tiene $BR con IP; no toco la red"
		else
			$B ifconfig "$BR" "$IP" netmask "$MASK" up 2>/dev/null \
				&& log "bridge de RouterOS $BR sin IP: puesta $IP"
		fi
		exit 0
	fi

	# Sin bridge de RouterOS: bridge Linux volatil.
	if [ ! -d /sys/class/net/br0 ]; then
		$B brctl addbr br0 2>/dev/null
		for n in ether1 ether2 ether3 ether4 lan1 lan2 lan3 lan4; do
			$B brctl addif br0 "$n" 2>/dev/null
		done
		$B ifconfig br0 up 2>/dev/null
		log "br0 creado con ether1..4/lan1..4"
	fi

	IF=br0
	if [ -n "$VLAN" ]; then
		$B vconfig add br0 "$VLAN" 2>/dev/null
		IF="br0.$VLAN"
	fi
	$B ifconfig "$IF" "$IP" netmask "$MASK" up 2>/dev/null

	# Diagnostico HTTP de ultimo recurso: sirve /flash/rw (logs de sysinit,
	# sermgr, www, loader.trace). No sustituye a www; solo permite leer los
	# logs cuando la GUI no arranca. Se queda en 8080.
	if [ ! -e /flash/rw/httpd.started ]; then
		: > /flash/rw/httpd.started 2>/dev/null || true
		$B httpd -p 8080 -h /flash/rw 2>/dev/null \
			&& log "httpd diag en 8080 (/flash/rw)"
	fi

	# DHCP solo en el fallback Linux; si RouterOS manda, no se arranca.
	if [ ! -s /flash/rw/udhcpd.pid ]; then
		cat > /flash/rw/udhcpd.conf <<DHCP
start 192.168.1.100
end 192.168.1.199
interface $IF
opt router $IP
opt dns $IP
option subnet $MASK
lease_file /flash/rw/udhcpd.leases
pidfile /flash/rw/udhcpd.pid
DHCP
		$B udhcpd -f /flash/rw/udhcpd.conf >/dev/null 2>&1 &
		log "dhcp en $IF (192.168.1.100-199)"
	fi

	i=$((i + 1))
	$B sleep 20
done
NETUP
		chmod 755 $R/bin/netup 2>/dev/null || true
		# netup corre antes que sysinit; sin el modulo bridge, brctl falla
		# con "Package not installed" y no hay red de gestion.
		BRKO=$R/lib/modules/5.6.3/net/bridge/bridge2.ko
		if [ -f "$BRKO" ]; then
			/bin/busybox insmod "$BRKO" >/tmp/bridge.err 2>&1 \
				&& echo "  bridge2.ko cargado para netup" \
				|| echo "  bridge2.ko: $(cat /tmp/bridge.err 2>/dev/null)"
		fi
		# CGI de diagnostico para ejecutar ordenes desde el puerto 8080
		# mientras www/login estan bloqueados. Solo existe en este
		# arranque de desarrollo; no forma parte de la GUI.
		mkdir -p $R/flash/rw/cgi-bin 2>/dev/null || true
		cat > $R/flash/rw/cgi-bin/run <<'CGI'
#!/bin/sh
echo "Content-Type: text/plain"
echo
cd /
if [ "$REQUEST_METHOD" = POST ]; then
	CMD=$(cat)
else
	CMD=${QUERY_STRING#cmd=}
fi
eval "$CMD" 2>&1
CGI
		chmod 755 $R/flash/rw/cgi-bin/run 2>/dev/null || true
		chroot $R /bin/busybox sh /bin/netup >/dev/null 2>&1 &
		echo "  red de gestion: ayudante netup armado"
		# Flag de arranque del U-Boot: el firmware stock lo resetea
		# desde /etc/init.d/bootcount con fw_setenv. Sin ese reset,
		# iboot acabaria intentando el banco de recuperacion.
		# Las herramientas se compilan estaticas en el initramfs y se
		# copian al overlay; el contador solo se toca si sysinit ha
		# levantado la web/API.
		if [ -x /usr/sbin/fw_printenv ]; then
			cp /usr/sbin/fw_printenv $R/bin/fw_printenv 2>/dev/null || true
			cp /usr/sbin/fw_setenv   $R/bin/fw_setenv   2>/dev/null || true
			chmod 755 $R/bin/fw_printenv $R/bin/fw_setenv 2>/dev/null || true
			cat > $R/flash/rw/fw_env.config <<'FWENV'
/dev/ubi0:env1 0x0 0x1f000
/dev/ubi0:env2 0x0 0x1f000
FWENV
			cat > $R/bin/bootok <<'BOOTOK'
#!/bin/sh
# Flag de arranque del U-Boot, equivalente a /etc/init.d/bootcount del
# stock. Solo actua con rootfs_0 y si sysinit responde; si no, deja el
# flag para que iboot pueda intentar la recuperacion.
B=/bin/busybox
LOG=/flash/rw/bootok.log
CUR=""
for a in $($B cat /proc/cmdline 2>/dev/null); do
	case "$a" in root=*) CUR=${a#root=}; CUR=${CUR#ubi0:} ;; esac
done
case "$CUR" in
	rootfs_0) ;;
	*) echo "$($B date '+%Y-%m-%d %H:%M:%S') actual=$CUR no es rootfs_0; flag intacto" >> "$LOG"; exit 0 ;;
esac
svc_up() {
	for f in /proc/net/tcp /proc/net/tcp6; do
		[ -r "$f" ] || continue
		$B grep -q ':0050 ' "$f" 2>/dev/null && return 0
		$B grep -q ':0017 ' "$f" 2>/dev/null && return 0
		$B grep -q ':200B ' "$f" 2>/dev/null && return 0
	done
	return 1
}
i=0
while [ "$i" -lt 12 ]; do
	$B sleep 10
	if svc_up; then break; fi
	i=$((i + 1))
done
if ! svc_up; then
	echo "$($B date '+%Y-%m-%d %H:%M:%S') sysinit no responde; flag de arranque intacto" >> "$LOG"
	exit 0
fi
# La contrasena de admin solo se fija en el primer arranque. Se borra
# la linea del autorun persistente para que un cambio posterior en
# RouterOS no se pierda en el siguiente reinicio.
$B sed -i '/user set admin password/d' /flash/rw/autorun.scr \
	/flash/rw/store/autorun.scr 2>/dev/null || true
ROOTVOL=$(/bin/fw_printenv -c /flash/rw/fw_env.config -n root_vol 2>/dev/null)
if [ -z "$ROOTVOL" ]; then
	echo "$($B date '+%Y-%m-%d %H:%M:%S') fw_printenv no lee root_vol; flag intacto" >> "$LOG"
	exit 0
fi
if [ "$ROOTVOL" != "rootfs_0" ]; then
	echo "$($B date '+%Y-%m-%d %H:%M:%S') root_vol=$ROOTVOL no es rootfs_0; flag intacto" >> "$LOG"
	exit 0
fi
if /bin/fw_setenv -c /flash/rw/fw_env.config boot_cnt_primary 0 2>>"$LOG"; then
	echo "$($B date '+%Y-%m-%d %H:%M:%S') boot_cnt_primary=0 (rootfs_0)" >> "$LOG"
else
	echo "$($B date '+%Y-%m-%d %H:%M:%S') fallo al escribir boot_cnt_primary" >> "$LOG"
fi
BOOTOK
			chmod 755 $R/bin/bootok 2>/dev/null || true
			chroot $R /bin/busybox sh /bin/bootok >/dev/null 2>&1 &
			echo "  flag de arranque U-Boot: ayudante bootok armado"
		fi
					echo "  sysinit: $(ls -l $R/sbin/sysinit 2>&1)"
			if [ "$ROS_POST" = 1 ]; then
				cat > $R/bin/postdiag <<'POST'
#!/bin/sh
cd /
sleep 45
exec >/dev/console 2>&1
echo
echo "=== POSTDIAG: procesos tras sysinit ==="
/bin/busybox ps
echo "=== POSTDIAG: sockets unix ==="
/bin/busybox cat /proc/net/unix
echo "=== POSTDIAG: montajes ==="
/bin/busybox cat /proc/mounts
echo "=== POSTDIAG: mensajes ==="
if [ -f /flash/rw/logs/messages ]; then
	/bin/busybox tail -n 120 /flash/rw/logs/messages
else
	echo "sin /flash/rw/logs/messages"
fi
echo "=== POSTDIAG: backtrace ==="
if [ -f /flash/rw/logs/backtrace.log ]; then
	/bin/busybox tail -n 80 /flash/rw/logs/backtrace.log
else
	echo "sin backtrace.log"
fi
echo "=== POSTDIAG: dmesg final ==="
/bin/busybox dmesg | /bin/busybox tail -n 80
echo "=== POSTDIAG: matando login colgado ==="
for n in login parser; do
	for p in $(/bin/busybox pidof $n 2>/dev/null); do
		echo "  kill -9 $n $p"
		/bin/busybox kill -9 $p 2>/dev/null
	done
done
sleep 1
echo "=== POSTDIAG: shell de inspeccion ==="
exec /bin/busybox sh -i 0</dev/console 1>/dev/console 2>&1
POST
				chmod 755 $R/bin/postdiag 2>/dev/null || true
				( cd $R && chroot $R /bin/busybox sh /bin/postdiag ) &
				echo "  postdiag: armado (45 s)"
			fi
			if [ "$ROS_LOGINWRAP" = 1 ] && [ -x $R/nova/bin/login ]; then
				cp -a $R/nova/bin/login $R/nova/bin/login.real 2>/dev/null || true
				cat > $R/nova/bin/login <<'LOGINWRAP'
#!/bin/sh
echo "$(date) argv:$*" >> /flash/rw/login.log 2>/dev/null
exec /nova/bin/login.real "$@"
LOGINWRAP
				chmod 755 $R/nova/bin/login 2>/dev/null || true
				echo "  loginwrap: /nova/bin/login -> shell (real en login.real)"
			fi
			if [ "$ROS_STARTSTORE" = 1 ]; then
				echo "  sstore real: lo inicia sysinit con sus argumentos normales"
			fi
			if [ "$ROS_PANICDUMP" = 1 ]; then
				( sleep 55; echo "===PANIC0==="; /bin/busybox cat $R/flash/nova/logs/panic0.log 2>/dev/null; echo "===PANIC1==="; /bin/busybox cat $R/flash/nova/logs/panic1.log 2>/dev/null; echo "===PS==="; /bin/busybox chroot $R /bin/busybox ps; echo "===PANIC_END===" ) >/dev/console 2>&1 &
				echo "  panic dump: 55 s"
			fi
			if [ "$ROS_STARTUSER" = 1 ]; then
				( cd $R && chroot $R /bin/busybox setsid /bin/busybox sh -c 'while :; do while [ ! -S /ram/novasock ] || [ ! -S /ram/storereg ] || [ ! -S /ram/logsocket ]; do /bin/busybox sleep 1; done; /bin/busybox sleep 2; /nova/bin/user; echo "user exit=$?" >> /flash/rw/user.log; /bin/busybox sleep 10; done' >$R/flash/rw/user.log 2>&1 ) &
				echo "  user: espera a /ram/storereg (desde 20 s)"
				# Si sysinit se queda esperando a sstore, loader no llega a
				# arrancar. En cuanto exista storereg, lanzarlo desde aqui.
				( cd $R && chroot $R /bin/busybox setsid /bin/busybox sh -c 'while :; do while [ ! -S /ram/storereg ]; do /bin/busybox sleep 1; done; /bin/busybox sleep 8; if ! /bin/busybox pidof loader >/dev/null 2>&1; then /nova/bin/loader; fi; /bin/busybox sleep 5; done' >$R/flash/rw/loader.manual.log 2>&1 ) &
				echo "  loader: ayudante tras /ram/storereg"
			fi
			if [ "$ROS_REALLOGIN" = 1 ]; then
				( cd $R && chroot $R /bin/busybox setsid /bin/busybox sh -c 'sleep 55; exec /nova/bin/login console' </dev/console >/dev/console 2>&1 ) &
				echo "  login modo console a 55 s"
			fi
			if [ "$ROS_TTYSHELL" = 1 ]; then
				cat > $R/bin/ttyshell <<'TTY'
#!/bin/sh
sleep 95
# sysinit/loader ya inicia sermgr y www; no duplicarlos fuera del loader.
/bin/busybox ifconfig lan4 192.168.1.2 netmask 255.255.255.0 up 2>/dev/null || true
(
	while :; do
		{
			echo "=== WebFig diagnostics ==="
			/bin/busybox cat /proc/uptime
			echo "--- processes ---"
			/bin/busybox ps
					echo "--- process executable links ---"
					for d in /proc/[0-9]*; do
						[ -r "$d/cmdline" ] || continue
						echo "PID ${d##*/}: $(/bin/busybox readlink "$d/exe" 2>/dev/null)"
						/bin/busybox tr '\000' ' ' < "$d/cmdline" 2>/dev/null
						echo
					done
			echo "--- store paths ---"
			for p in /ram/storereg /ram/novasock /ram/run /rw/store /nova/store/sermgr /flash/rw/loader.trace; do
				if [ -e "$p" ]; then /bin/busybox ls -ld "$p"; else echo "missing: $p"; fi
			done
			echo "--- store files (names/sizes only) ---"
			/bin/busybox ls -ln /rw/store 2>&1
					echo "--- cfg.0000 printable strings ---"
					/bin/busybox strings /rw/store/cfg.0000 2>/dev/null | /bin/busybox head -n 160
					for f in /flash/rw/sermgr.log /flash/rw/www.log /flash/rw/user.log /flash/rw/sstore.log /flash/nova/logs/messages /flash/nova/logs/log; do
						if [ -r "$f" ]; then echo "--- $f ---"; /bin/busybox tail -n 100 "$f"; fi
					done
			echo "--- related unix sockets ---"
			/bin/busybox grep -E 'storereg|sermgr|www|user' /proc/net/unix 2>/dev/null
			echo "--- loader trace (service negotiation, filtered) ---"
			/bin/busybox grep -aE 'no settings, asking sermgr|set www enabled=|connect failed' /flash/rw/loader.trace 2>/dev/null | /bin/busybox tail -n 60
		} > /home/web/diag.txt.tmp 2>&1
		/bin/busybox mv /home/web/diag.txt.tmp /home/web/diag.txt 2>/dev/null || true
		/bin/busybox sleep 5
	done
) >/dev/null 2>&1 &
exec /bin/busybox sh -i 0</dev/ttyS0 1>/dev/ttyS0 2>/dev/ttyS0
TTY
				chmod 755 $R/bin/ttyshell 2>/dev/null || true
				( cd $R && chroot $R /bin/busybox setsid /bin/busybox sh /bin/ttyshell ) &
				echo "  ttyshell: armado (90 s, ttyS0)"
			fi
			if [ "$ROS_TTYSHELL" = 0 ]; then
				cat > $R/bin/webdiag <<'WEBDIAG'
#!/bin/sh
B=/bin/busybox
$B sleep 95
$B ifconfig lan4 192.168.1.2 netmask 255.255.255.0 up 2>/dev/null || true
while :; do
	{
		echo "=== RouterOS diagnostic ==="
		$B cat /proc/uptime
		$B ps
		$B ls -ln /rw/store 2>&1
		$B strings /rw/store/cfg.0000 2>/dev/null | $B head -n 160
		for f in /flash/rw/sstore.log /flash/rw/sermgr.log /flash/rw/www.log /flash/rw/user.log /flash/rw/netup.log /flash/rw/logs/messages; do
			if [ -r "$f" ]; then echo "--- $f ---"; $B tail -n 120 "$f"; fi
		done
		$B cat /proc/net/unix
		} > /flash/rw/diag.txt.tmp 2>&1
		$B mv /flash/rw/diag.txt.tmp /flash/rw/diag.txt 2>/dev/null || true
		$B sleep 5
done
WEBDIAG
				chmod 755 $R/bin/webdiag 2>/dev/null || true
				( cd $R && chroot $R /bin/busybox setsid /bin/busybox sh /bin/webdiag ) >/dev/null 2>&1 &
				echo "  webdiag: IP 192.168.1.2 y diagnostico HTTP a 95 s, sin consola"
			fi
			echo "  lanzando /sbin/sysinit (switch_root)"
			# sysinit y el login que cuelga de el tienen que recibir la
			# consola como stdin/stdout/stderr. Si heredan un fd que no es
			# un TTY, /nova/bin/login arranca en modo headLess y el prompt
			# de la consola se queda sin proceso que lo atienda.
			exec switch_root $R /sbin/sysinit start </dev/console >/dev/console 2>&1
	fi
	echo "  no se pudo montar el rootfs de RouterOS, sigo con el initramfs"
fi

[ -f /etc/network.conf ] && . /etc/network.conf
HOSTNAME=${HOSTNAME:-ed500}
STATIC_IP=${STATIC_IP:-192.168.1.2}
STATIC_MASK=${STATIC_MASK:-24}
STATIC_GW=${STATIC_GW:-192.168.1.1}
HTTP_PORT=${HTTP_PORT:-80}
hostname "$HOSTNAME"

mkdir -p /run /var/log
echo
echo "=================================================="
echo " $HOSTNAME - initramfs viva (kernel $(uname -r))"
echo "=================================================="
head -12 /proc/cpuinfo
echo

# --- esperar al switch ---
# El driver gswip va por detras: necesita el conduit y el reset del RCU, asi
# que la primera vez queda en probe diferido. Sin esta espera, el init corre
# antes de que existan los lan* y se queda sin red.
ifaces() {
	sed -n 's/^ *\([a-z0-9]*\):.*/\1/p' /proc/net/dev | grep -v '^lo$'
}

ESPERA=0
while [ "$ESPERA" -lt 30 ]; do
	HAY=0
	for n in $(ifaces); do
		case "$n" in lan*) HAY=1 ;; esac
	done
	[ "$HAY" = 1 ] && break
	ESPERA=$((ESPERA + 1))
	sleep 1
done
echo "espera de interfaces: ${ESPERA}s"

# --- red: puertos del switch en un bridge ---
# eth0/cbm0 es el maestro de DSA; puentearlo con sus propios puertos rompe el
# datapath. Por eso se prefieren los lan* y solo se cae en eth*/cbm* cuando no
# hay puertos DSA.
echo "interfaces:"
for n in $(ifaces); do
	echo "  $n $(cat /sys/class/net/$n/operstate 2>/dev/null)"
done

BRPORTS=""
for n in $(ifaces); do
	case "$n" in lan*) BRPORTS="$BRPORTS $n" ;; esac
done
if [ -z "$BRPORTS" ]; then
	for n in $(ifaces); do
		case "$n" in eth*|cbm*) BRPORTS="$BRPORTS $n" ;; esac
	done
fi

COUNT=0
for n in $BRPORTS; do COUNT=$((COUNT + 1)); done

if [ "$COUNT" -eq 0 ]; then
	echo "red: no hay interfaces (el driver Ethernet no ha creado ninguna)"
	echo "--- dmesg: switch / conduit / phy ---"
	dmesg 2>/dev/null | grep -iE "gswip|cbm|xrx|conduit|mdio|phy|dsa" | tail -25
	echo "--- dmesg: ultimas lineas ---"
	dmesg 2>/dev/null | tail -20
	iface=""
else
	echo "red: puertos:$BRPORTS"
	# El maestro de DSA (el conduit del SoC) tiene que estar arriba ANTES de
	# abrir los puertos: dsa_slave_open() devuelve -ENETDOWN si el maestro
	# esta down, y el ifconfig del puerto falla con "Network is down". El
	# maestro no se puentea con sus propios puertos.
	for m in cbm0 eth0; do
		if [ -d /sys/class/net/$m ]; then
			ifconfig "$m" up && echo "red: maestro $m up"
		fi
	done
	for n in $BRPORTS; do
		ifconfig "$n" up || echo "red: no he podido abrir $n"
	done

	# un solo puerto -> directo; varios -> bridge (asi da igual la boca)
	if [ "$COUNT" -ge 2 ] && command -v brctl >/dev/null 2>&1; then
		brctl addbr br0 2>/dev/null
		for n in $BRPORTS; do
			brctl addif br0 "$n" 2>/dev/null
		done
		ifconfig br0 up 2>/dev/null
		iface=br0
	else
		for n in $BRPORTS; do iface=$n; break; done
	fi

	echo "red: usando $iface"
	if command -v udhcpc >/dev/null 2>&1; then
		udhcpc -i "$iface" -t 3 -T 2 -n -q >/tmp/dhcp.log 2>&1
	fi

	CUR_IP=""
	if ifconfig "$iface" 2>/dev/null | grep -q "inet addr"; then
		CUR_IP=$(ifconfig "$iface" | sed -n 's/.*inet addr:\([0-9.]*\).*/\1/p' | head -1)
	fi

	if [ -z "$CUR_IP" ]; then
		echo "red: sin DHCP, IP fija $STATIC_IP/$STATIC_MASK"
		ifconfig "$iface" "$STATIC_IP" netmask 255.255.255.0 up 2>/dev/null
		[ -n "$STATIC_GW" ] && route add default gw "$STATIC_GW" 2>/dev/null
		CUR_IP=$STATIC_IP
	fi

	echo "red: $CUR_IP en $iface"
fi

# --- diagnostico del enlace -------------------------------------------
# Una foto del estado de los PHY y del switch. Va a la consola y a
# /www/enlace.txt: sin ella, un puerto caido no distingue entre "el PHY no
# ve cable" y "el driver no se entera del link".
diag_enlace() {
	echo "--- puertos ---"
	for m in cbm0 eth0; do
		[ -d /sys/class/net/$m ] || continue
		printf '  %-4s %-8s carrier=%-6s (maestro)\n' "$m" \
			"$(cat /sys/class/net/$m/operstate 2>/dev/null)" \
			"$(cat /sys/class/net/$m/carrier 2>/dev/null)"
	done
	for n in lan1 lan2 lan3 lan4; do
		[ -d /sys/class/net/$n ] || continue
		phy=$(readlink /sys/class/net/$n/phydev 2>/dev/null)
		printf '  %-4s %-8s carrier=%-6s phy=%s\n' "$n" \
			"$(cat /sys/class/net/$n/operstate 2>/dev/null)" \
			"$(cat /sys/class/net/$n/carrier 2>/dev/null)" \
			"${phy##*/}"
	done
	if [ -x /bin/phyreg ]; then
		for n in lan1 lan2 lan3 lan4; do
			[ -d /sys/class/net/$n ] || continue
			echo "  -- $n (BMCR BMSR ANAR 1000C 1000S) --"
			phyreg "$n" 0 1 4 9 10 2>&1 | sed 's/^/    /'
		done
	fi
	if [ -x /bin/swstats ] && [ -d /sys/class/net/lan1 ]; then
		echo "--- contadores del switch (lan1) ---"
		swstats lan1 2>&1 | sed 's/^/    /'
	fi
	echo "--- nand ---"
	if [ -r /proc/mtd ]; then
		sed 's/^/    /' /proc/mtd
	else
		echo "    sin /proc/mtd"
	fi
	ls -l /dev/mtd* 2>/dev/null | sed 's/^/    /'
	if [ -d /sys/class/net/lan1 ]; then
		echo "--- prueba de datapath: 3 pings al PC ---"
		[ -c /dev/mem ] || mknod /dev/mem c 1 1 2>/dev/null
		echo -n "    phyaddr lan1: "
		devmem 0x1c003d50 2>/dev/null
		if [ -x /bin/swstats ]; then
			swstats lan1 2>/dev/null | grep -E 'tx_packets|rx_packets|TxGoodPkts|TxDroppedPkts|RxGoodPkts' | sed 's/^/    antes: /'
		fi
		ping -c 3 -W 1 192.168.1.161 >/dev/null 2>&1
		if [ -x /bin/swstats ]; then
			swstats lan1 2>/dev/null | grep -E 'tx_packets|rx_packets|TxGoodPkts|TxDroppedPkts|RxGoodPkts' | sed 's/^/    despues: /'
		fi
	fi
	echo "--- dmesg: gswip / phy ---"
	dmesg 2>/dev/null | grep -iE 'gswip|xway|phy[0-9]|mii|link is|link up' | tail -20
}

sleep 6
{ echo "=== enlace tras 6 s ==="; diag_enlace; } > /www/enlace.txt 2>&1
cat /www/enlace.txt
(
	sleep 10
	echo
	echo "=== enlace tras 16 s ==="
	diag_enlace
) >> /www/enlace.txt 2>&1 &
(
	sleep 10
	diag_enlace
) &
[ -z "${CUR_IP:-}" ] && CUR_IP=$STATIC_IP

# --- servidores ---
mkdir -p /www/cgi-bin
if [ -x /bin/busybox ] || command -v httpd >/dev/null 2>&1; then
	httpd -p "$HTTP_PORT" -h /www 2>/dev/null && echo "web: http://$CUR_IP/"
fi
if command -v telnetd >/dev/null 2>&1; then
	telnetd -l /bin/sh 2>/dev/null && echo "telnet: puerto 23 (root, sin password)"
fi
if [ -x /usr/sbin/dropbear ]; then
	[ -f /etc/dropbear/dropbear_rsa_host_key ] || \
		/usr/sbin/dropbearkey -t rsa -f /etc/dropbear/dropbear_rsa_host_key >/dev/null 2>&1
	/usr/sbin/dropbear -R -p 22 2>/dev/null && echo "ssh: puerto 22 (root, sin password)"
fi

# --- log accesible por web (para cuando no hay consola) ---
dmesg > /www/dmesg.txt 2>/dev/null
{
	echo "hostname: $HOSTNAME"
	echo "kernel:   $(uname -a)"
	echo "ip:       $CUR_IP en $iface"
	echo
	echo "== interfaces =="
	ifconfig -a 2>/dev/null
	echo
	echo "== rutas =="
	route -n 2>/dev/null
	echo
	echo "== bridge =="
	brctl show 2>/dev/null
} > /www/estado.txt 2>/dev/null
(
	while true; do
		sleep 30
		dmesg > /www/dmesg.txt 2>/dev/null
	done
) &

echo
echo "estado: http://$CUR_IP/   ·   consola: ttyLTQ0"
echo "log del arranque: http://$CUR_IP/dmesg.txt"
echo "escribe 'exit' para reiniciar."
echo
setsid cttyhack /bin/sh 2>/dev/null || exec /bin/sh
