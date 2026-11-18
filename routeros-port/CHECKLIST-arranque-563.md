# First boot test of 5.6.3 on the ED500

## Before powering on (5 minutes)

1. **Console cable**: COM4, 115200 8N1. This is the point that failed last time
   (the board was on and silent, but because of the kernel without console, not
   the cable). Check it responds: with the router off there is no echo; on
   power-on `ROM VER: 2.1.0` must appear.
2. **Network cable**: PC on any LAN port (`lan1..lan4`). Any port is fine: the
   init bridges them all in `br0`.
3. **TFTP**: server listening on `0.0.0.0:69` with root `routeros-port/out`.
   Check that `uImage-563` is there and weighs what it should.
4. **PC**: static IP `192.168.1.160/24` on the Ethernet interface (already
   configured).

## Booting

Power on and, during the 3 seconds of `bootdelay`, send CR to break autoboot.
`IOPSYS 2 grx500 #` should appear. Then:

```
tftpboot 0x80500000 uImage-563
bootm 0x80500000
```

If you miss the prompt: power off, power on and hammer CR (that is what
`catch_final.py` does).

## What should appear on console, in order

1. `Linux version 5.6.3` — the correct kernel (factory says 4.9.109).
2. `Console: colour dummy device` / `console [ttyLTQ0] enabled` — console alive.
3. `gswip-xrx500 1c000000.switch: probed GSWIP version ...` — the ported
   switch.
4. `DSA: tree 0 setup` and `lan1..lan4` — switch ports.
5. `cbm` / `xrx500-conduit` — the conduit giving the CPU its output.
6. `network: ports: ...` and `network: 192.168.1.2 on br0` — init configured
   the network.
7. `web: http://192.168.1.2/` and `telnet: port 23`.
8. Prompt `~ #`.

## How to get in if the console fails again

From the PC, without touching anything:

```
ping 192.168.1.2
telnet 192.168.1.2        # root, no password
http://192.168.1.2/       # status page
```

## Problem signals and what they mean

| symptom | likely cause |
|---|---|
| Nothing on console, but 1 Gbps link | kernel without console or UART disconnected |
| `ROM VER` in a loop | the uImage entry is not the ELF's |
| Boots but no `lan*` | the GSWIP driver did not bind (see dmesg) |
| `lan*` but no `cbm0` | the conduit did not probe (reserved memory or DMA) |
| `br0` without IP | the switch does not forward and the bridge kept no ports |
| `request_firmware` fails | PHY firmware (embedded and in /lib/firmware) |

## After booting (real goal: RouterOS)

If the kernel comes up and there is network, the next step is to give it **its
rootfs** (the squashfs of the original npk) instead of our initramfs. That
requires UBI/UBIFS or mounting over NFS, and is the step before seeing `/nova`
and WebFig.

## Failures already fixed in advance (previous audit)

These five would have shown up tomorrow and are already resolved in
`out/uImage-563`:

| failure | consequence | fix |
|---|---|---|
| `CONFIG_SERIAL_LANTIQ` did not exist | silent console | Kconfig `LANTIQ \|\| INTEL_MIPS` |
| `CONFIG_BRIDGE` off | no bridge, IP on a random port | enabled |
| busybox without `ip`, `awk`, `wc` | init failed silently, no IP | init rewritten with `ifconfig`/`route`/`brctl` |
| GPHY firmware missing | ports without link | embedded + `/lib/firmware/lantiq/` |
| no GRX500 clock driver | ASC in `-EPROBE_DEFER` forever | ported `clk-grx500` + CGU from 6.18 |

The `earlycon=lantiq,0x16600000` in the bootargs does not depend on any of
that: if the rest fails, at least you can see where booting goes.

## Third block: boot chain verified by hand

Checked byte by byte before powering on:

- `uImage-563`: magic `27051956`, valid header **and** data CRC, `os=Linux`,
  `arch=MIPS`, `type=kernel`, uncompressed, load = entry = `0x80500000`.
- The payload starts at `kernel_entry` (`sync; ehb; mfc0 t1,c0_config`), not an
  ELF.
- Embedded DTB: `__dtb_end - __dtb_start` = **11296 B**, exactly `norrland.dtb`.
- Timer: `intel-mips/time.c` takes `mips_hpt_frequency` from the CPU node's
  clock (`<&cgu 150>` = `CLK_CPU`), and the CGU driver registers it. Without
  it there is no clocksource.
- Console: `lantiq,asc` with clocks `<&cgu 13>` and `<&cgu 117>`, both
  registered.
- `/init` inside the cpio is **0755**; busybox has `sed`, `cut`, `grep`,
  `ifconfig`, `brctl`, `route`, `udhcpc`, `httpd`, `telnetd` and `dmesg`
  compiled in.

**DSA tag ported**: the XRX500 puts an 8-byte header on the CPU port, but DSA
only had the 4-byte `gswip` tag. `tag_gswip3` (enum, driver, Kconfig) has been
ported and the switch now declares `DSA_TAG_PROTO_GSWIP3`. Without this the
ports come up but no packet passes.

## Fifth block: memory map clarified (not a bug)

It looked odd to load at `0x80500000` while the DTB says RAM is at
`0x20000000`. Checked against the factory kernel: **it loads at `0xa0020000`**,
i.e. physical `0x20020000`. On this SoC with EVA, KSEG0/KSEG1 map from
`0x20000000`, so `0x80500000` is physical `0x20500000`, inside RAM. All
consistent: `mem=224M@512M`, `memory@20000000` and our load address.

The kernel occupies `0x20500000`–`0x20B6_7000` (6.7 MB) and the CBM pool
starts at `0x23800000`: 33 MB of margin, no overlap.

**Reboot resolved**: the DTB carries a `reboot` node with `compatible =
"syscon-reboot"` (child of chiptop, offset 0x10, bit 0x40000000). With
`CONFIG_POWER_RESET` + `CONFIG_POWER_RESET_SYSCON` enabled, `reboot` works and,
since the bootargs carry `panic=20`, a panic **reboots the board on its own**.
The catcher goes back to waiting for U-Boot, so a failure retries without
touching power.

If `syscon-reboot` did not hit the right register, reboot does nothing (it does
not break booting). In that case each attempt needs a power cut again.

## Fourth block: dry-run boot already tested

- **TFTP integrated in the catcher**: `catch_final.py` serves the image itself
  (port 69, and if busy, 6969 + `setenv tftpdstp`). Tested with a real client:
  download of 6,702,516 bytes, **identical byte for byte**.
- **Addresses fixed before loading**: `setenv ipaddr 192.168.1.1` and
  `setenv serverip 192.168.1.160`, so it does not depend on whatever was left
  in U-Boot's environment. The PC's Ethernet also has aliases on
  192.168.0/30/31/32.160.
- **Automatic retry**: if the kernel reboots, the catcher goes back to waiting
  for U-Boot and reloads, until the 3 h window runs out.
- **Log over web**: init leaves `/www/dmesg.txt` and `/www/estado.txt`. Without
  console, `http://192.168.1.2/dmesg.txt` gives the full boot.
- **Automatic verdict**: at the end the catcher prints on one line what happened
  (`booted + switch + lan1 + network + http + shell`, `PANIC`, or
  `bootm silent`), without reading the whole log.
- **`ignore_loglevel`** in the bootargs: the kernel prints debug messages too
  from the very first instant.
- **A bug of mine fixed**: init put `eth0` (DSA master) into the bridge along
  with its own ports, which breaks the datapath. Now it uses only `lan*` and
  only falls back to `eth*`/`cbm*` if there are no DSA ports.

## Second block: what RouterOS needed from the kernel

The kernel compiled, but the configuration was not enough for a real userspace.
These six were **off** and would have killed `/nova` in the first second, with
no message:

| option | without it |
|---|---|
| `CONFIG_FUTEX` | no threads: any binary with pthreads dies |
| `CONFIG_EPOLL` / `EVENTFD` / `TIMERFD` / `SIGNALFD` | `/nova`'s event loop does not start |
| `CONFIG_POSIX_TIMERS` / `AIO` | timers and async I/O |
| `CONFIG_NETFILTER` / `NF_CONNTRACK` | firewall cannot hook in |
| `CONFIG_MIPS_FP_SUPPORT` | SIGILL if any binary uses the FPU |
| `CONFIG_TMPFS` / `SHMEM` | no `/dev/shm` nor `/tmp` in RAM |
| `CONFIG_SQUASHFS`+`XZ`, `BLK_DEV_LOOP` | cannot mount its rootfs |
| `CONFIG_IP_MULTIPLE_TABLES` | RouterOS routes with tables: without this, no routes |

An initramfs with busybox uses none of that, so the failure would not have been
seen until RouterOS' rootfs was loaded inside. All are now `y`.

## Pending for RouterOS' real rootfs

1. **NAND**: the 5.6.3 tree has no `lantiq-xrx500-nand.c` (6.18 does). To
   mount its rootfs from flash it must be ported. Alternative without NAND:
   put its file tree in the initramfs and `switch_root`.
2. **vermagic**: our kernel says `5.6.3 mod_unload MIPS32_R2 32BIT`. If their
   `.ko` were built with SMP/preempt, they will not load until a kernel is
   built with those flags.
3. **License**: `/nova` may ask for a license tied to the hardware. There it
   stops, no patching.

## Rollback

None of this writes to NAND: `tftpboot` + `bootm` go to RAM. To go back to the
factory firmware, cut power and let it boot on its own.
