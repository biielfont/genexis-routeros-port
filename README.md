# Genexis Pure ED500 — native RouterOS port

Native (not patched `.npk`) port of MikroTik RouterOS to the **Genexis Pure
ED500** router: Intel/Lantiq GRX350 SoC, MIPS big-endian interAptiv. Goal:
boot a native Linux 5.6.3 kernel with SoC drivers, then attempt to load the
original RouterOS rootfs to reach `/nova` and WebFig.

> No `.npk` is patched or used to bypass licensing. If `/nova` requires a
> license bound to the hardware, work stops there.

## Status

- Kernel 5.6.3 **builds and boots in dry runs**: `out/uImage-563` is
  6,702,556 B, valid header and data CRC, load = entry = `0x80500000`,
  embedded DTB `norrland.dtb` (11,296 B).
- Console, clocks, GSWIP3 DSA tag, initramfs, reboot-on-panic and TFTP
  catcher are in place.
- **First real boot on hardware has not happened yet** (no physical access).
- Ethernet/NAND/switch drivers for this SoC are still pending.

See [`PROGRESS.md`](./PROGRESS.md) for the full progress map.

## Layout

```
routeros-port/
  build-563.sh              # config + build + uImage
  catch_final.py            # TFTP-integrated catcher with verdict
  tftplib.py                # TFTP server thread
  09-FLASHEAR-Y3.md         # .y3 container format and flashing
  ARRANQUE-TFTP.md          # TFTP boot instructions
  CHECKLIST-arranque-563.md # first-boot checklist
  NOTES-5.6.3-port.md       # DSA driver port notes
  out/
    uImage-563              # artifact to boot (6.7 MB)
    norrland.dtb            # embedded DTB
  refs/                     # platform patches and DTS fragments
  tree/                     # ported arch/mips + drivers
  logs/                     # serial and boot logs
```

## Building

Toolchain: `/opt/toolchain/bin/mips-buildroot-linux-gnu-`. Kernel tree:
`/opt/ros-port/linux-5.6.3` (GPL sources published by MikroTik). Build scripts
run inside WSL (kali-linux). See `routeros-port/build-563.sh`.

## Hardware

- Genexis Pure ED500, GRX350, MIPS big-endian interAptiv.
- Console: COM4, 115200 8N1.
- TFTP: UDP 69 (fallback 6969).
- PC Ethernet alias: `192.168.1.160/24`.

## License

Kernel sources are MikroTik's GPL-published tree. This repository contains
porting work, notes and tooling. RouterOS userland is not redistributed here.
