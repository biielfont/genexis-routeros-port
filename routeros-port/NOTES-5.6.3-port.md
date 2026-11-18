# Native port: GSWIP XRX500 driver from 6.18 → kernel 5.6.3 (RouterOS')

## Why 5.6.3

RouterOS 7.17 mipsbe runs on Linux **5.6.3** (verified: `lib/modules/5.6.3/...`
inside the npk's squashfs). The GPL sources for that kernel are published
(linux-5.6.3.tgz + linux-5.6.3.patch.gz, mirror on tikoci/mikrotik-gpl).

## Tree state

- `/opt/ros-port/linux-5.6.3` — kernel with MikroTik's patch, `intel-mips`
  platform hooked into `arch/mips/Kconfig`, `norrland.dts` and `norrland.dtb`
  already built.
- `drivers/net/ethernet/lantiq/` — vendor stack: `xrx500-cbm.c` (2879 lines,
  the conduit that on 6.18 creates `cbm0`), `cqm/`, `dma/`, `tmu/`. Already
  compiled.
- **What is missing**: the switch driver. 5.6.3 only ships the generic
  `lantiq_gswip.c` (danube/amazon/xway), which does not know the XRX500.

## Port scaffold (created)

- `drivers/net/dsa/xr/` with copies from 6.18:
  - `lantiq_gswip_common.c` (2138 lines)
  - `lantiq_gswip_xrx500.c` (1313)
  - `lantiq_gswip.h` (390)
  - `lantiq_pce.h`, `lantiq_pce_xrx500.h`
  - `xr_compat.h` (compatibility layer, see below)
- Hooked into `drivers/net/dsa/Makefile` + `Kconfig`
  (`CONFIG_NET_DSA_XR_GSWIP`).
- `tag_gswip3.c` (128 lines) is copied into `xr/` but **does not compile
  there**: it needs `net/dsa/tag.h` and `dsa_priv.h`. It must move to
  `net/dsa/` and `DSA_TAG_PROTO_GSWIP3` must be added to `include/net/dsa.h`.
- Iteration script: `routeros-port/xr-iter.sh` (copies the compat layer,
  patches the include, compiles and summarizes errors).

## Real API of this 5.6.3 (verified)

- `dsa_to_port(ds, p)`, `dsa_is_user_port`, `dsa_is_cpu_port` exist.
- **No** public `dsa_user_to_port()` or `dsa_slave_to_port()`: the netdev→port
  mapping only lives in `net/dsa/dsa_priv.h`.
- **No** `dsa_switch_for_each_*` iterators nor `dsa_cpu_ports()`.
- `dev->dsa_ptr` is `struct dsa_port *` (not `dsa_switch_tree *`).
- `struct dsa_device_ops.rcv(skb, dev, pt)` carries `pt`; 6.18 does not.
- `struct dsa_device_ops` uses `.overhead`, not `.needed_headroom`.
- `.port_vlan_add` returns `void` (6.18 returns `int`).
- `dp->bridge_dev`, not `dp->bridge`; **no** `struct dsa_bridge`.
- Kbuild uses gnu89: `-std=gnu11` must be forced per file.

## Compat already resolved in `xr_compat.h`

`dev_err_probe`, `regmap_set_bits`, `regmap_clear_bits`,
`devm_of_mdiobus_register`, `dsa_port_is_user/cpu`,
`dsa_port_bridge_dev_get`, iterators `dsa_switch_for_each_{port,user_port,cpu_port}`
and `dsa_cpu_ports(ds)` used as an **expression** (CPU port mask).

## Compile errors: 108 → 124 (and falling)

Remaining categories:

1. `dsa_cpu_ports(ds)` used as a mask → implement as a function returning a
   mask (the current macro is an iterator, must be split).
2. Bridge: `dp->bridge`, `struct dsa_bridge`, FID per bridge, and callbacks
   `port_pre_bridge_flags` / `port_bridge_flags` (do not exist in 5.6.3).
3. `ethtool_eth_mac_stats`, `ethtool_rmon_stats`, `ethtool_pause_stats`,
   `ethtool_keee`… (35 errors): the stats API is new.
4. `phylink_config.supported_interfaces` and `.mac_capabilities` do not exist:
   must use `phylink_validate`/`phylink_mac_ops` from 5.6.
5. `ds->mtu_enforcement_ingress`, `ds->max_num_bridges`,
   `switchdev_obj_port_vlan.vid`.

## Compile progress

116 → 41 → 30 → 19 → **15 errors**.

Scripts (in `routeros-port/`), run in this order:

1. `patch_reduce.py` — disables ethtool stats, eee, bridge flags,
   phylink_get_caps; rewrites the ops table to 5.6.3's.
2. `patch_bridge.py` — standalone FID, join/leave signatures, `vid`→`vid_begin`,
   drops `mtu_enforcement_ingress`.
3. `patch_ops.py` — fdb_add/del without `struct dsa_db`, fdb_dump dropped,
   CTL1000, REGMAP_UPSHIFT, clk_bulk.
4. `patch_api.py` — regmap with its own bus, phylink, vlan signatures.
5. `xr-iter.sh` — compiles and summarizes (use after every patch).

## New facts verified

- `reg_stride` in 5.6.3 **only validates alignment** (`IS_ALIGNED`), it does
  not scale the address: it cannot substitute `reg_shift`. A `regmap_bus` with
  raw callbacks is needed: `read(ctx, reg_buf, reg_len, val_buf, val_len)` and
  `write(ctx, data, count)` — note, the signature I wrote (reg,val) is 6.x's.
- `struct phylink_mac_ops` in 5.6.3:
  - `mac_config(config, unsigned int mode, const struct phylink_link_state *state)`
  - `mac_link_down(config, mode, interface)`
  - `mac_link_up(config, mode, interface, struct phy_device *phy)` — **without**
    speed, duplex or pause: those go in `mac_config` via `state`.

## Pending (15 errors)

1. `regmap_bus` with the raw 5.6 signature (raw read/write).
2. `gswip_port_vlan_filtering`: the real signature does not match the regex
   used.
3. `ethtool_puts()` → write with `strscpy` to 32 bytes and advance.
4. `ethtool_rmon_hist_range` table (trim).
5. Move speed/duplex/pause from `mac_link_up` to `mac_config` (use `state->`).
6. `dsa_switch_shutdown` does not exist → `#if 0`.
7. `ds->phylink_mac_ops` and `ds->max_num_bridges` do not exist in 5.6.3:
   phylink is created with `dsa_port_phylink_create()` from the driver's per-port
   callbacks.
8. `hw_info->phylink_get_caps` (and `gswip_xrx500_r_...`) still referenced in
   the model table: drop the field or the pointer.
9. `DSA_TAG_PROTO_GSWIP3`: add the enum in `include/net/dsa.h` and move
   `tag_gswip3.c` to `net/dsa/`.

## Strategy for the first boot (reduce, do not port everything)

Goal: **flat switch working** (CPU + lan1..lan4, one VLAN, no bridge offload)
to get network and boot RouterOS' rootfs. Left out, to be added later:
ethtool statistics, tc flower, mirror, VLAN filtering, mtu enforcement, bridge
offload.

## Nov 18 — audit before first boot

Failures found and fixed before powering on (see
CHECKLIST-arranque-563.md): SERIAL_LANTIQ (Kconfig), CONFIG_BRIDGE, init
without ip/awk/wc, GPHY firmware, clock driver for GRX500 ported from 6.18,
and the userspace block (FUTEX, EPOLL, EVENTFD, TIMERFD, SIGNALFD, AIO,
POSIX_TIMERS, TMPFS, SQUASHFS, LOOP, IP_MULTIPLE_TABLES, NETFILTER,
NF_CONNTRACK, MIPS_FP_SUPPORT).

Pending: NAND xrx500 (only in 6.18), vermagic SMP of RouterOS' `.ko`, and
putting its rootfs in the initramfs for switch_root.
