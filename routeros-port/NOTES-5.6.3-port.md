# Port nativo: driver GSWIP XRX500 de 6.18 -> kernel 5.6.3 (el de RouterOS)

## Por qué 5.6.3
RouterOS 7.17 mipsbe corre sobre Linux **5.6.3** (comprobado: `lib/modules/5.6.3/...`
dentro del squashfs del npk). Las fuentes GPL de ese kernel estan publicadas
(linux-5.6.3.tgz + linux-5.6.3.patch.gz, espejo en tikoci/mikrotik-gpl).

## Estado del arbol
- `/opt/ros-port/linux-5.6.3` — kernel con el parche de MikroTik, plataforma
  `arch/mips/intel-mips` enganchada en `arch/mips/Kconfig`, `norrland.dts` y
  `norrland.dtb` ya construidos.
- `drivers/net/ethernet/lantiq/` — stack del vendor: `xrx500-cbm.c` (2879 lineas,
  el conduit que en 6.18 crea `cbm0`), `cqm/`, `dma/`, `tmu/`. Ya compilado.
- **Lo que falta**: el driver del switch. 5.6.3 solo trae `lantiq_gswip.c`
  generico (danube/amazon/xway), que no conoce el XRX500.

## Andamio del port (creado)
- `drivers/net/dsa/xr/` con copias de 6.18:
  - `lantiq_gswip_common.c` (2138 lineas)
  - `lantiq_gswip_xrx500.c` (1313)
  - `lantiq_gswip.h` (390)
  - `lantiq_pce.h`, `lantiq_pce_xrx500.h`
  - `xr_compat.h` (capa de compatibilidad, ver abajo)
- Enganchado en `drivers/net/dsa/Makefile` + `Kconfig` (`CONFIG_NET_DSA_XR_GSWIP`).
- `tag_gswip3.c` (128 lineas) esta copiado en `xr/` pero **no compila ahi**:
  necesita `net/dsa/tag.h` y `dsa_priv.h`. Debe moverse a `net/dsa/` y anadir
  `DSA_TAG_PROTO_GSWIP3` a `include/net/dsa.h`.
- Script de iteracion: `routeros-port/xr-iter.sh` (copia el compat, parchea el
  include, compila y resume errores).

## API real de este 5.6.3 (comprobada)
- `dsa_to_port(ds, p)`, `dsa_is_user_port`, `dsa_is_cpu_port` existen.
- **No** existen `dsa_user_to_port()`, `dsa_slave_to_port()` publicas: el mapeo
  netdev->puerto solo esta en `net/dsa/dsa_priv.h`.
- **No** existen los iteradores `dsa_switch_for_each_*` ni `dsa_cpu_ports()`.
- `dev->dsa_ptr` es `struct dsa_port *` (no `dsa_switch_tree *`).
- `struct dsa_device_ops.rcv(skb, dev, pt)` lleva `pt`; 6.18 no.
- `struct dsa_device_ops` usa `.overhead`, no `.needed_headroom`.
- `.port_vlan_add` devuelve `void` (6.18 devuelve `int`).
- `dp->bridge_dev`, no `dp->bridge`; **no** hay `struct dsa_bridge`.
- Kbuild usa gnu89: hay que forzar `-std=gnu11` por fichero.

## Compat ya resuelta en `xr_compat.h`
`dev_err_probe`, `regmap_set_bits`, `regmap_clear_bits`,
`devm_of_mdiobus_register`, `dsa_port_is_user/cpu`, `dsa_port_bridge_dev_get`,
iteradores `dsa_switch_for_each_{port,user_port,cpu_port}` y `dsa_cpu_ports(ds)`
usado como **expresion** (mascara de puertos CPU).

## Errores de compilacion: 108 -> 124 (y bajando)
Categorias que quedan:
1. `dsa_cpu_ports(ds)` usado como mascara -> implementar como funcion que
   devuelve mascara (el macro actual es iterador, hay que separarlo).
2. Bridge: `dp->bridge`, `struct dsa_bridge`, FID por bridge, y las callbacks
   `port_pre_bridge_flags` / `port_bridge_flags` (no existen en 5.6.3).
3. `ethtool_eth_mac_stats`, `ethtool_rmon_stats`, `ethtool_pause_stats`,
   `ethtool_keee`... (35 errores): la API de stats es nueva.
4. `phylink_config.supported_interfaces` y `.mac_capabilities` no existen:
   hay que usar `phylink_validate`/`phylink_mac_ops` de 5.6.
5. `ds->mtu_enforcement_ingress`, `ds->max_num_bridges`, `switchdev_obj_port_vlan.vid`.

## Progreso de compilacion
116 -> 41 -> 30 -> 19 -> **15 errores**.

Scripts (en `routeros-port/`), se ejecutan en este orden:
1. `patch_reduce.py` — desactiva stats ethtool, eee, flags de bridge, phylink_get_caps;
   reescribe la tabla de ops a la de 5.6.3.
2. `patch_bridge.py` — FID standalone, firmas join/leave, `vid`->`vid_begin`,
   fuera `mtu_enforcement_ingress`.
3. `patch_ops.py` — fdb_add/del sin `struct dsa_db`, fdb_dump fuera,
   CTL1000, REGMAP_UPSHIFT, clk_bulk.
4. `patch_api.py` — regmap con bus propio, phylink, firmas vlan.
5. `xr-iter.sh` — compila y resume (usar despues de cada parche).

## Hechos nuevos comprobados
- `reg_stride` en 5.6.3 **solo valida alineacion** (`IS_ALIGNED`), no escala la
  direccion: no sirve como sustituto de `reg_shift`. Hay que usar un
  `regmap_bus` con callbacks crudos: `read(ctx, reg_buf, reg_len, val_buf, val_len)`
  y `write(ctx, data, count)` — ojo, la firma que puse (reg,val) es la de 6.x.
- `struct phylink_mac_ops` de 5.6.3:
  - `mac_config(config, unsigned int mode, const struct phylink_link_state *state)`
  - `mac_link_down(config, mode, interface)`
  - `mac_link_up(config, mode, interface, struct phy_device *phy)` — **sin** speed,
    duplex ni pausa: eso va en `mac_config` via `state`.

## Pendiente (15 errores)
1. `regmap_bus` con la firma cruda de 5.6 (raw read/write).
2. `gswip_port_vlan_filtering`: la firma real no coincide con el regex usado.
3. `ethtool_puts()` -> escribir con `strscpy` a 32 bytes y avanzar.
4. Tabla `ethtool_rmon_hist_range` (recortar).
5. Mover speed/duplex/pausa de `mac_link_up` a `mac_config` (usa `state->`).
6. `dsa_switch_shutdown` no existe -> `#if 0`.
7. `ds->phylink_mac_ops` y `ds->max_num_bridges` no existen en 5.6.3: el
   phylink se crea con `dsa_port_phylink_create()` a partir de las callbacks
   por puerto del driver.
8. `hw_info->phylink_get_caps` (y `gswip_xrx500_r_...`) siguen referenciados en
   la tabla de modelos: quitar el campo o el puntero.
9. `DSA_TAG_PROTO_GSWIP3`: anadir el enum en `include/net/dsa.h` y mover
   `tag_gswip3.c` a `net/dsa/`.

## Estrategia para el primer arranque (reducir, no portar todo)
Objetivo: **switch plano funcionando** (CPU + lan1..lan4, una VLAN, sin offload
de bridge) para tener red y arrancar el rootfs de RouterOS. Se dejan fuera, y se
anaden despues: estadisticas ethtool, tc flower, mirror, VLAN filtering,
mtu enforcement, bridge offload.

## 18 nov - auditoria previa al primer arranque

Fallos encontrados y corregidos antes de encender (ver CHECKLIST-arranque-563.md):
SERIAL_LANTIQ (Kconfig), CONFIG_BRIDGE, init sin ip/awk/wc, firmware GPHY, driver
de relojes GRX500 portado desde 6.18, y el bloque de userspace (FUTEX, EPOLL,
EVENTFD, TIMERFD, SIGNALFD, AIO, POSIX_TIMERS, TMPFS, SQUASHFS, LOOP,
IP_MULTIPLE_TABLES, NETFILTER, NF_CONNTRACK, MIPS_FP_SUPPORT).

Pendiente: NAND xrx500 (solo esta en 6.18), vermagic SMP de los .ko de RouterOS,
y meter su rootfs en initramfs para el switch_root.
