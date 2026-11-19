# Genexis Pure ED500 — native RouterOS port

Native (not patched `.npk`) port of MikroTik RouterOS to the **Genexis Pure
ED500** router: Intel/Lantiq GRX350 SoC, MIPS big-endian interAptiv. Goal: boot
MikroTik's own Linux 5.6.3 kernel with the SoC drivers, then load the original
RouterOS rootfs to reach `/nova` and WebFig.

> No `.npk` is patched and no licensing is bypassed. RouterOS licensing is
> MikroTik's; this repository only contains our own patches and tools.

## Status

Working today, verified on hardware:

- Kernel 5.6.3 builds and **boots on the ED500** over TFTP into RAM.
- Serial console, clocks and reboot-on-panic are in place.
- **Ethernet works at 1 Gbps**: GSWIP switch, DSA and XWAY PHY (TX/RX both fixed).
- **NAND works**: Macronix MX30LF1G18AC, 128 MiB SLC, software BCH ECC.
- **RouterOS boots**: overlay over its squashfs rootfs, `flash.ko` loads, and a
  shell can be obtained inside its root filesystem.

Still blocked, with the reason documented:

- **RouterOS networking**: its `packet_hook.ko`, `switch.ko` and `bridge2.ko`
  depend on MikroTik's binary *fastpath* (`fast_path_*`, `netif_receive_try_fp`,
  `skb_bin_*`), which is not in the GPL sources, and there is no RouterOS driver
  for this SoC's switch.
- **RouterOS licence**: the demo needs a MikroTik-formatted disk; the NAND here
  holds the stock Adamo firmware and reads fail with `ecc unrecoverable error`.
  A CHR (x86) licence does not apply to MIPS BE.

See [`routeros-port/README.md`](./routeros-port/README.md) for the full
technical write-up and [`PROGRESS.md`](./PROGRESS.md) for the investigation log.

## Layout

```
routeros-port/            # the port itself: build scripts, patches, diagnostics
  README.md               # full technical write-up
  build-563.sh            # config + build + uImage
  parche_arranque.py      # all kernel-tree patches (idempotent)
  init-initramfs.sh       # initramfs init: overlay, network, RouterOS handover
  catch_final.py          # TFTP-integrated U-Boot catcher
  check_*.sh              # diagnostic scripts used during the investigation
  refs/                   # platform patches and DTS fragments
  tree/                   # ported arch/mips + drivers
logs/                    # serial and boot logs
```
