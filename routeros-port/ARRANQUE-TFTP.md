# Booting the ported kernel on the Genexis Pure ED500

All of this runs **in RAM**: nothing is written to NAND, the Genexis firmware
on flash stays untouched. If anything fails, power off and boot as usual.

## 1. What is in `out/`

| File | Purpose |
|---|---|
| `uImage` (3.9 MB) | boot with `bootm` |
| `vmlinux.elf` (30 MB) | boot with `bootelf` |
| `vmlinux.bin.gz` (2.4 MB) | faster to push over TFTP; decompressed on the PC |
| `norrland.dtb` | only in case you want to pass it separately |

Kernel contents: `Linux 5.6.3` + `intel-mips` platform (GRX350),
embedded DTB `norrland`, static busybox in the initramfs.

Facts confirmed from your U-Boot log:

- CPU/DDR at **800/800 MHz** (already set in the DTS, `CPU_HZ`).
- Console **`ttyLTQ0`** at 115200 (Lantiq's asc does not use `ttyS0`).
- DRAM **224 MiB**, consistent with `mem=224M@512M` → DDR at `0x20000000`,
  which is exactly the platform's `PHYS_OFFSET`.

## 2. Serving over TFTP

From this folder (Windows, with Python installed):

```
python tftp-server.py out --port 69
```

If port 69 is busy (Tftpd64 or another), use `--port 6969` and in U-Boot
`setenv tftpdstp 6969`.

Find the IP of the serving PC (`ipconfig` on Windows). Under WSL with
`networkingMode=mirrored` the IP is the same as Windows'.

## 3. ED500 U-Boot (console 115200 8N1)

```
setenv ipaddr 192.168.1.10
setenv serverip 192.168.1.100
setenv netmask 255.255.255.0

# option A: uImage
tftpboot 0x82000000 uImage
bootm 0x82000000

# option B: ELF (better if bootm complains about the architecture)
tftpboot 0x82000000 vmlinux.elf
bootelf 0x82000000
```

Boot arguments are provided by the embedded DTB
(`console=ttyLTQ0,115200 earlycon mem=224M@512M`), so there is no need for
`setenv bootargs`. If you want to force them:

```
setenv bootargs "console=ttyLTQ0,115200 earlycon mem=224M@512M board=norrland"
```

Note: `bootm` relocates the image to the ELF load address (`0x80500000`,
which with `PHYS_OFFSET 0x20000000` is physical `0x20500000`). Loading at
`0x82000000` is only the staging buffer.

## 4. What you should see

```
[    0.000000] Linux version 5.6.3 ...
[    0.000000] bootconsole [early0] enabled
[    0.000000] CPU0 revision is: 0001a900 (MIPS interAptiv)
[    0.000000] Intel MIPS interAptiv SoC
[    0.000000] Determined physical RAM map: memory: 0e000000 @ 02000000 (usable)
[    0.000000] GIC: using split EOI/confirm mode
...
==================================================
 GRX350 / norrland - initramfs alive (kernel 5.6.3)
==================================================
```

If it reaches `initramfs alive`, the port is alive on the real SoC and only
peripherals remain to be added (NAND, switch, PCIe).

## 5. If it does not boot: what to check

| Symptom | Likely cause | What to change |
|---|---|---|
| Nothing on console | UART mis-addressed | `earlycon=lantiq,0x16600000` in `bootargs` (writes without reprogramming the baud, inherits U-Boot's) |
| Console starts then dies when handing over to `ttyLTQ0` | the `asc` clock is not 100 MHz | adjust `UART_HZ` in the DTS |
| Hangs after "Intel MIPS..." | wrong CPU frequency → GIC/timer | `CPU_HZ` in `norrland.dts` |
| `Bad Magic Number` | `bootm` does not accept the image | use `bootelf` |
| Immediate reboot | early exception | boot with `earlycon` and `ignore_loglevel` |

The real CPU frequency appears in the Genexis U-Boot log
(`CPU: 800 MHz` or similar) or in `/proc/cpuinfo` of the original firmware;
with that data, recompile changing only `#define CPU_HZ` in `norrland.dts`.

## 6. Recompiling after a change

```
wsl -d kali-linux -u root -- bash /mnt/c/Users/BFR/Documents/Genexis/routeros-port/04-build-initramfs.sh
wsl -d kali-linux -u root -- bash -c 'cd /opt/ros-port/linux-5.6.3 && make ARCH=mips \
  CROSS_COMPILE=/opt/toolchain/bin/mips-buildroot-linux-gnu- -j4 vmlinux'
```

The artifacts in `out/` are regenerated with `05-package.sh`.

## 7. Virtual tests (no router)

`06-qemu-test.sh` boots a **clean** 5.6.3 compiled with the same toolchain,
the same initramfs and the same endianness (big-endian) as the ED500 kernel,
and verifies userspace end to end:

```
wsl -d kali-linux -u root -- bash /mnt/c/Users/BFR/Documents/Genexis/routeros-port/06-qemu-test.sh

  OK   kernel 5.6.3 boots
  OK   initramfs mounted and /init executed
  OK   initramfs banner on console
  OK   interactive busybox shell
  OK   kernel CPU table
  OK   full kernel boot
RESULT: PASS
```

What it covers: that the kernel boots, that the initramfs unpacks, that `/init`
runs, that `/dev/console` exists, that busybox (static ELF32 MSB) runs and
that the serial console serves. The full log is left in `out/qemu-malta.log`.

What it does **not** cover: QEMU does not emulate the GRX350 (GIC at
`0x12320000`, asc at `0x16600000`, NAND, switch). The `prom.c`/`irq.c`/`time.c`
path of `arch/mips/intel-mips` can only be validated on real hardware; in QEMU
the `malta` machine with CPU `24Kc` is used because `-cpu I7200` (interAptiv)
does not boot on that machine.

## 8. Known limitation of MikroTik's GPL patch

The published patch is not self-contained: with a full configuration
(e.g. `CONFIG_NET_RX_BUSY_POLL=y`) references appear to
`dev->napi_defer_hard_irqs` and `napi->defer_hard_irqs_count`, fields that are
mainline 5.10 and that MikroTik has in its tree but **does not** include in
the patch:

```
net/core/dev.c:6519: error: 'struct net_device' has no member named 'napi_defer_hard_irqs'
```

For H3 (full RouterOS config) there are two exits: disable
`NET_RX_BUSY_POLL` in the config (the code is excluded by `#ifdef`) or restore
the original 5.6.3 implementation of `busy_poll_stop()`. The current minimal
config does not touch that file, so it compiles.
