# Progress map — Genexis Pure ED500 native RouterOS port

Last updated: 2026-11-18. Status reflects work verified without hardware.

## Phase 0 — Investigation

- [x] SoC identified: Intel/Lantiq GRX350, MIPS big-endian interAptiv.
- [x] RouterOS 7.17 mipsbe runs on Linux 5.6.3 (verified in npk squashfs).
- [x] GPL kernel sources located (linux-5.6.3 + patch, mirror tikoci/mikrotik-gpl).
- [x] Memory map clarified: EVA maps KSEG0 `0x80500000` → physical `0x20500000`,
      inside `memory@20000000`; coherent with `mem=224M@512M`, factory kernel
      (`0xa0020000`) and validated `tftpboot`.

## Phase 1 — Kernel 5.6.3 builds

- [x] Kernel compiles: `build=0`, `vmlinux` 76,376,716 B.
- [x] `out/uImage-563` = 6,702,556 B; valid header and data CRC;
      `load=entry=0x80500000`, `os=5`, `arch=5`, `type=2`, `comp=0`.
- [x] Payload starts at `kernel_entry` (`sync; ehb; mfc0 t1,c0_config`).
- [x] Embedded DTB verified: `__dtb_end - __dtb_start` = `norrland.dtb`
      (11,296 B with `panic=20`).
- [x] Console: `CONFIG_SERIAL_LANTIQ=y`, earlycon `lantiq,0x16600000`,
      alias `serial0` → `ttyLTQ0`.
- [x] Clock driver ported (`clk-grx500` + CGU, `CLK_SSX4`=13,
      `GCLK_UART`=117, `CLK_CPU`=150) → serial and `mips_hpt_frequency`
      use a real clock.
- [x] Userspace config complete: FUTEX, EPOLL, EVENTFD, TIMERFD, SIGNALFD,
      AIO, POSIX_TIMERS, MULTIUSER, TMPFS, SHMEM, BLOCK, SQUASHFS(+XZ),
      BLK_DEV_LOOP, IP_MULTIPLE_TABLES, NETFILTER, NF_CONNTRACK,
      MIPS_FP_SUPPORT, INOTIFY_USER, SYSVIPC, FHANDLE,
      POWER_RESET + POWER_RESET_SYSCON.
- [x] GSWIP3 DSA tag ported: enum 17, `net/dsa/tag_gswip3.c`,
      Kconfig/Makefile; driver declares `DSA_TAG_PROTO_GSWIP3`;
      `CONFIG_NET_DSA_TAG_GSWIP3=y`, object built, `gswip3` string in vmlinux.

## Phase 2 — Initramfs

- [x] GPHY firmware embedded (`/lib/firmware/lantiq/xrx500-phy-fw.bin`) +
      `CONFIG_EXTRA_FIRMWARE`.
- [x] Init rewritten without `ip`/`awk`/`wc` (uses `ifconfig`/`route`/`brctl`).
- [x] Bridge uses only `lan*` ports (never the DSA master).
- [x] Diagnostics: `dmesg` if no interfaces; publishes `/www/dmesg.txt` and
      `/www/estado.txt`; `/init` is 0755.

## Phase 3 — Boot infrastructure

- [x] Catcher `catch_final.py` with integrated TFTP (`tftplib.py`), fallback
      69→6969 + `setenv tftpdstp`, `setenv ipaddr/serverip`, size check,
      automatic verdict and retry after reboot.
- [x] Real TFTP download verified byte-identical (6,702,556 B).
- [x] DTB audit: reserved-memory CBM (18 MiB std / 8 MiB jbo), conduit
      `ethernet@0` with DMA by phandle, second switch `status = "disabled"`,
      `phy-mode = "internal"` present in 5.6.3, cbm/hdma/conduit compiled and
      linked.
- [x] Reboot resolved: `syscon-reboot` node + `CONFIG_POWER_RESET` +
      `POWER_RESET_SYSCON`; `panic=20` makes a panic reboot the board alone.

## Phase 4 — First real boot (NOT DONE)

- [ ] Power on the board and capture U-Boot prompt.
- [ ] `tftpboot 0x80500000 uImage-563` then `bootm`.
- [ ] Verify on console: `Linux version 5.6.3`, `gswip`, `lan1..lan4`,
      `network: 192.168.1.2 on br0`, prompt.
- [ ] Reach via `telnet 192.168.1.2` or `http://192.168.1.2/dmesg.txt`.
- [ ] Use `reboot` to iterate without cutting power.

Blocked: no physical access; someone must power the board once. The catcher runs
in BACKGROUND (PID 17308, 3 h window) serving TFTP on 6969.

## Phase 5 — Ethernet / switch (pending)

- [ ] Port `lantiq-xrx500-nand.c` (only in 6.18) or put rootfs in initramfs
      + `switch_root`.
- [ ] Recover stats/EEE/bridge-offload in the DSA driver.
- [ ] Evaluate SMP (vermagic of RouterOS' `.ko`).

## Phase 6 — RouterOS rootfs (pending)

- [ ] Load original RouterOS rootfs (squashfs from npk) instead of initramfs.
- [ ] Inspect `/nova` and WebFig.
- [ ] License check: if `/nova` requires a hardware-bound license, stop (no
      patching).

## Open risks

- NAND driver missing in 5.6.3 (only in 6.18).
- vermagic: our kernel reports `5.6.3 mod_unload MIPS32_R2 32BIT`; their `.ko`
  built with SMP/preempt will not load until matching flags.
- `syscon-reboot` may not hit the right register: reboot would do nothing (does
  not break booting, but each attempt needs a power cut).
- Hard hang still needs a power cut: `intel_grx500_wdt.c` only exists in 6.18.
- MikroTik's GPL patch is not self-contained (NET_RX_BUSY_POLL references).
- No Ethernet driver for GRX500 yet: switch needs CBM/DQM (block H2c).

## Artifacts

- `routeros-port/out/uImage-563` — 6,702,556 B (boot this).
- `routeros-port/out/norrland.dtb` — 11,296 B.
- `routeros-port/out/qemu-malta.log` — virtual dry-run log.
