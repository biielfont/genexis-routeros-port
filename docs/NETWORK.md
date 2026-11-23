# Red, usuarios y VLANs

Este documento describe cómo queda la red del ED500 en el build #96 y qué
partes siguen pendientes de probar en placa. La idea es que el router sea
usable **sin consola** y que, si RouterOS no puede montar su bridge, el
initramfs deje una red de gestión funcional.

## Dos capas, una sola direccion

### 1. RouterOS: `/flash/autorun.scr`

`sysinit` consulta varias rutas de autorun (`/flash/autorun.scr`, `/rw`,
`/rw/store` y branding). El init escribe el script en `/flash/autorun.scr` y lo
copia a todas ellas en cada boot (es volatil, como `/flash`), para que no se
quede con una copia vacia. Contiene:

- contrasena de `admin` (`ed500` por defecto, o `ros.pass=...` en los
  bootargs de U-Boot);
- bridge `bridge` con `lan1..lan4` (solo los que RouterOS vea);
- `192.168.88.1/24` en el bridge;
- pool DHCP `192.168.88.100-200` y servidor DHCP en el bridge;
- un ejemplo comentado de VLAN 10.

Si `bridge2.ko` no carga, las ordenes del autorun fallan y RouterOS se queda
sin bridge. No es fatal: entra la segunda capa.

### 2. Initramfs: `/bin/netup`

`netup` arranca en segundo plano tras `sysinit`. Espera 60 s y:

1. Levanta `cbm0` y `lan1..lan4`.
2. Si RouterOS ya creo un bridge con IP, no toca nada.
3. Si hay un bridge de RouterOS sin IP, le pone `192.168.1.2/24`.
4. Si no hay bridge, crea `br0` con `lan1..lan4`, le pone `192.168.1.2/24` y
   arranca un DHCP Linux (`192.168.1.100-199`).
5. Si los bootargs traen `mgmt.vlan=NN`, crea `br0.NN` con `vconfig` y pone la
   IP ahi.

El resultado practico:

| Escenario | Direccion de gestion |
|---|---|
| RouterOS con bridge y autorun | `http://192.168.88.1/` |
| RouterOS sin bridge | `http://192.168.1.2/` |
| VLAN de gestion `mgmt.vlan=10` | `http://192.168.1.2/` en `br0.10` |

`netup` escribe su traza en `/flash/rw/netup.log`. No escribe NAND.

## Usuarios

- `admin` queda con la contrasena de `autorun.scr`.
- Se puede cambiar sin recompilar:
  `ros.pass=otra-clave` en los bootargs de U-Boot.
- Para cambiarla ya arrancado, por consola serie:

  ```bash
  python tools/rosconsole.py --password ed500 --nueva "otra-clave"
  ```

- `tools/rosconsole.py` entra byte a byte (el login de RouterOS no usa FIFO),
  completa el dialogo `new password>` si RouterOS lo pide y ejecuta comandos:

  ```bash
  python tools/rosconsole.py --cmd "/system resource print"
  python tools/rosconsole.py --script config.rsc
  ```

La base de usuarios de RouterOS vive en `/rw` (tmpfs en este port), asi que
la contrasena se regenera en cada arranque. Cuando la instalacion persistente
en NAND este resuelta, el autorun tendra que dejar de tocar `admin`.

## VLANs

El kernel del build #96 lleva:

- `CONFIG_VLAN_8021Q=y` (core de VLAN, `vlan_vid_add/del`);
- `CONFIG_BRIDGE_VLAN_FILTERING=y` (filtrado por VLAN en el bridge);
- `CONFIG_BRIDGE_NETFILTER=y` y `CONFIG_BRIDGE_EBTABLES=y`;
- `CONFIG_JUMP_LABEL=y` (`nf_hooks_needed`, que `bridge2.ko` necesita);
- `CONFIG_USER_NS=y` (`make_kuid`, que `packet_hook.ko` necesita);
- `CONFIG_XFRM=y` + IPComp (tuneles XFRM que `packet_hook.ko` necesita);
- `CONFIG_NET_SCHED`, `CONFIG_NET_CLS_ACT`, netfilter/NAT, MII, I2C, GPIO,
  HWMON y LEDS_CLASS para los modulos de RouterOS.

En RouterOS, una VLAN se crea sobre el bridge:

```rsc
/interface vlan add name=vlan10 interface=bridge vlan-id=10
/ip address add address=192.168.10.1/24 interface=vlan10
```

En Linux, para la VLAN de gestion:

```
mgmt.vlan=10
```

en los bootargs; `netup` crea `br0.10` y pone `192.168.1.2` ahi.

## Que falta y que no se debe dar por hecho

- **`packet_hook.ko`**: el build #96 exporta `netif_receive_try_fp` (el
  `net_device` virtual que crea `fp_init`), el #99 quita GPL-only y el #102
  corrige el ABI de `struct net_device`. En QEMU malta 5.6.3 el modulo carga;
  el kernel ya llama a `rx_handler_hook`/`tx_handler_hook` y `packet_hook` los
  registra. Falta probar en placa que registre los puertos.
- **`switch.ko`**: hasta el build #98 no cargaba: importa 10 simbolos que el
  kernel mainline exporta como GPL-only (`switchdev_*`, `alloc_workqueue`,
  `cancel_work_sync`, `destroy_workqueue`). El #99 los exporta sin esa
  restriccion, igual que el kernel de MikroTik; la auditoria da cero
  pendientes. `switch.ko` trae `alloc_switchdev` y notificadores switchdev,
  asi que puede enganchar los puertos DSA del GSWIP. En QEMU el #102 lo carga;
  falta probar en placa: si el userland pide un `switch_type` concreto, seguira
  diciendo "unknown switch type".
- **ABI de `struct net_device`**: el #102 deja `CONFIG_NET_CLS_ACT=n`. Sus dos
  `miniq_*` desplazaban `pcpu_refcnt` de 672 a 680; `packet_hook` usa 672 y
  hacia `dev_put()` sobre `todo_list.next` (NULL) al cargar. Con el layout de
  672, QEMU carga `packet_hook`/`phy_helper`/`switch`/`bridge2`.
- **Interfaces**: el #102 anade `ros-name = "ether1..4"` a los puertos DSA;
  `net` lee `/sys/class/net/lanX/of_node/ros-name` y crea `ether1..4`. Sin
  esa propiedad los puertos se quedan como `lan*` y RouterOS no los ve. El
  autorun y `netup` prueban `ether1..4` y `lan1..4`, asi el bridge no queda
  vacio si `net` renombra los puertos.
- **`bridge2.ko`**: el #102 deja `br_init` del kernel como stub (no registra
  pernet/link_ops/fdb) y retira 18 exportaciones `br_*` que el modulo vuelve a
  definir; se conserva `brioctl_set`, lo unico que `bridge2` pide al kernel.
  En QEMU `bridge2` carga y registra `bridge`; falta probarlo en placa.
- **Fastpath**: `netif_receive_try_fp` no es una funcion: es el `net_device`
  virtual de `fp_init`. El kernel llama a `rx_handler_hook` en
  `__netif_receive_skb_core` y a `tx_handler_hook` en `validate_xmit_skb`;
  `packet_hook` los registra y activa los static keys. Falta probar que los
  puertos queden registrados y que el camino rapido no rompa el trafico.
- **Persistencia**: `/flash` y `/rw` son tmpfs. Nada de esto sobrevive a un
  corte de corriente. La NAND sigue intacta.
- **WAN xDSL, no GPON**: el firmware stock extraido (`GNX-4.3.6.170-R`) trae
  `vrx518.ko`, `vrx518_tc.ko`, `drv_dsl_cpe_api.ko` y `/etc/init.d/dsl`; no
  trae ningun modulo PON/OMCI. La afirmacion anterior de "ED500 GPON" era
  incorrecta para esta unidad. RouterOS no tiene driver VRX518 y el de Genexis
  es binario para 4.9.109, asi que la WAN xDSL sigue sin soporte.

**Conclusión.** El kernel Linux tiene Ethernet DSA/GSWIP y `netup` da una red
de gestión funcional. El build #99 elimina la barrera GPL-only y deja
`switch.ko` cargable por primera vez; falta confirmar en placa si engancha los
puertos DSA. La WAN xDSL (VRX518) sigue sin driver en RouterOS; no es GPON. Un
MikroTik 100% exigiría ese driver de DSL y que el userland acepte el switch
DSA, y no se puede afirmar hasta verlo en hardware.

## Probar el lunes

1. El cazador ya esta corriendo en segundo plano (UDP 69, 72 h). No lances
   otro. Si el PC se reinicio, ejecuta `ARRANCAR-563.bat`.
2. Esperar `MikroTik Login:` y comprobar que el cazador libera COM4.
3. Probar las dos direcciones: `http://192.168.88.1/` y
   `http://192.168.1.2/`.
4. Entrar por consola:

   ```bash
   python tools/rosconsole.py --cmd "/interface print"
   python tools/rosconsole.py --cmd "/ip address print"
   ```

5. En RouterOS, comprobar `/interface print`, `/interface bridge print` y
   `/ip address print`. El fallback Linux escribe su traza en
   `/flash/rw/netup.log`; el archivo se puede listar con `/file print`, pero
   RouterOS no da un `cat` de consola.
6. Probar una VLAN:

   ```bash
   python tools/rosconsole.py --cmd "/interface vlan add name=vlan10 interface=bridge vlan-id=10"
   python tools/rosconsole.py --cmd "/ip address add address=192.168.10.1/24 interface=vlan10"
   ```

Si algo falla, el fallback `192.168.1.2` sigue disponible y la NAND no se ha
tocado.
