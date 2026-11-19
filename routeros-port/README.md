# RouterOS on the Genexis Pure ED500

Research port of **RouterOS 7.17 (mipsbe)** to the **Genexis Pure ED500**
(Intel/Lantiq **GRX350**, dual-core MIPS BE interAptiv), booting over **TFTP into
RAM** without writing anything to flash.

> **Legal notice.** This repository contains **no MikroTik software**. The
> RouterOS `.npk` and its rootfs are MikroTik's work and are downloaded from
> their site under their own terms and licence; only our own tools and patches
> are included here. It also contains no licence bypass: using RouterOS requires
> a valid licence.

---

## Current status

| Piece | State |
|---|---|
| MikroTik's 5.6.3 kernel built for GRX350 | **Works** |
| Serial console (`ttyLTQ0`, 115200) | **Works** |
| Ethernet: DSA + GSWIP switch + XWAY PHY | **Works at 1 Gbps** |
| NAND (Macronix MX30LF1G18AC, 128 MiB SLC) | **Detected and readable with BCH** |
| RouterOS boot (overlay over squashfs) | **Works** |
| RouterOS `flash.ko` loaded | **Works** |
| Shell inside the RouterOS rootfs | **Works** |
| Networking inside RouterOS (`ether`, bridge) | **No**: needs the binary *fastpath* and a switch driver that do not exist in the GPL sources |
| RouterOS demo licence | **No**: needs a disk with a MikroTik format that is not present here |

### The two walls, in detail

1. **RouterOS networking.** Its `packet_hook.ko`, `switch.ko` and `bridge2.ko`
   request symbols that exist **neither in the GPL sources nor in any `.ko` of
   the package**: `netif_receive_try_fp`, `fast_path_start_xmit`,
   `register_fast_path`, `skb_bin_*`, `phy_setup`, `custom_packet_hook_rx`…
   They belong to MikroTik's binary *fastpath*. On top of that, `switch.ko` is
   the driver for *their* switches (ath8327, mt7621…): there is no RouterOS
   driver for the GRX350's GSWIP.

2. **Licence.** RouterOS derives its *software ID* from the disk
   (`/dev/mtdblock0`), and here the NAND holds the Adamo firmware, not a
   MikroTik disk: reads fail with `ecc unrecoverable error` and the system ends
   at `Demo license expired!`. A **CHR** (x86) licence is useless here: this
   device is MIPS BE.

---

## Building

Requirements: an MIPS toolchain (`mips-buildroot-linux-gnu-`), U-Boot's `mkimage`
and MikroTik's GPL 5.6.3 kernel sources in `/opt/ros-port/linux-5.6.3`.

```bash
bash build-563.sh
```

The script:

1. Runs `parche_arranque.py` (every patch is **idempotent**).
2. Copies `init-initramfs.sh` and, if present, `ros/rootfs.squashfs` into the initramfs.
3. Builds `phyreg` and `swstats` (static) for diagnostics.
4. Adjusts the kernel config and builds `vmlinux`.
5. Packages `out/uImage-563` for `0x80500000`.

## Booting

```bash
python catch_final.py --horas 6 --pc-ip 192.168.1.161
```

It serves the image over TFTP, waits for U-Boot (192.168.1.1), loads it and runs
`bootm 0x80500000`. **Everything runs from RAM**: the NAND is never touched and
the stock firmware still boots if the catcher is not running.

On Windows, `ARRANCAR-563.bat` does the same with a double click.

---

## Layout

| Path | What it is |
|---|---|
| `build-563.sh` | Builds the 5.6.3 kernel and produces the `uImage` |
| `parche_arranque.py` | **All** tree patches, idempotent |
| `init-initramfs.sh` | Init: overlay, networking, diagnostics and RouterOS handover |
| `phyreg.c`, `swstats.c` | PHY (MDIO) and switch counter diagnostics |
| `catch_final.py` | U-Boot catcher + TFTP server |
| `consola.py`, `serialterm.py` | Serial console helpers |
| `refs/`, `tree/` | Platform references (DTS and patches) |
| `check_*.sh` | Diagnostic scripts used during the investigation |
| `patch_*.py` | Historical patches (the live one is `parche_arranque.py`) |
| `ros/` | **Not versioned**: the `.npk` and the rootfs go here |

### What `parche_arranque.py` does

- **Networking**: registers `.phylink_mac_config`, `.mac_link_up` and
  `.mac_link_down` in `gswip_switch_ops` (no TX without them) and passes the
  PHY's real speed/duplex instead of `UNKNOWN` (no RX without that).
- **NAND**: ports `lantiq-xrx500-nand.c` from 6.18 and adjusts the DTS.
- **RouterOS ABI**: exports symbols MikroTik had as GPL-only
  (`platform_bus_type`, `bus_find_device`, `device_match_name`, `mips_machtype`…),
  adds the RouterBOARD platform stubs and enables LZO.

---

## Findings that will save time to whoever continues

- RouterOS 7.17's kernel and the GPL tree are the **same 5.6.3**, and its 269
  `.ko` files carry the **same vermagic** (`5.6.3 mod_unload MIPS32_R2 32BIT`),
  which is why their modules load into a rebuilt kernel.
- `CONFIG_MODVERSIONS` must be **off** for that to work.
- `flash.ko` is proprietary (`license: unspecified`), so any GPL-only symbol
  makes it fail with `Unknown symbol`.
- The GRX350 has **no usable RTC**: without setting the date, RouterOS thinks it
  is 2010 and reports its demo licence as expired.
- RouterOS's `bash` lives in `/pckg/option`, which only exists with its packages
  mounted; for an emergency shell, copy a **static busybox** into the overlay
  (and name it `busybox`, otherwise it answers `applet not found`).
- `switch_root` with a shell as init panics on exit (`Attempted to kill init`);
  to inspect the system, use `chroot` and keep init alive.
