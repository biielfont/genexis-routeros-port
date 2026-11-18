# Installing via web / U-Boot with a custom `.y3`

## 1. The format is already decoded

A `.y3` of the ED500 is **a 1024-byte text header + UBIFS rootfs + pkginfo + MD5**.
Real header of the official firmware `GNX-4.3.6.170-R`:

```
IntenoIopY
version 5
integrity MD5SUM
git 71b8d1b
board NORRLAND
chip grx550
arch all mips_24kc_nomips16
model NORRLAND
release GNX-4.3.6.170-R
customer GNX
ubifsofs 1024
ubifs 44949504
pkginfoofs 44950528
pkginfo 28342
scrofs 44978870
scr 0
sigofs 44978870
sig 0          <-- NO cryptographic signature
md5ofs 44978870
md5 32
size 44978902
```

Two facts verified, not assumed:

- `sig 0`: **the update verifies no signature**, only an ASCII MD5.
- The MD5 covers everything from byte 0 up to `md5ofs`. Rebuilding the official
  firmware with our tool produces a file **identical byte for byte** to Genexis',
  so the container is fully understood.

Tool: `08-y3tool.py`

```
python3 08-y3tool.py info   out/ED500-stock-original.y3
python3 08-y3tool.py unpack out/ED500-stock-original.y3 /tmp/ext
python3 08-y3tool.py build  nuevo.y3 --ubifs rootfs.ubifs --pkginfo pk.txt \
        --release GNX-4.3.6.999-R
```

Rootfs geometry (deduced from the official UBIFS and respected when building):
PEB 128 KiB, LEB 124 KiB (`126976`), page 2 KiB. This matches the
**Macronix MX30LF1G18AC** NAND (1 Gbit SLC, 2 KiB page, 64 B OOB, 128 MiB)
whose ID is exactly the `0xc2 0xf1` that your U-Boot reports.

## 2. What is in `out/`

| File | What it is |
|---|---|
| `ED500-stock-original.y3` | official reference firmware (44.9 MB) |
| `ED500-stock-reconstruido.y3` | **byte-identical** to the official, produced by our tool |
| `ED500-nuestro-kernel.y3` | minimal UBIFS rootfs with our kernel (`/boot/uImage`, `/uImage`, `/kernel`) |

The third is the interesting one: 10 MB, `release GNX-4.3.6.999-R` (high
number to pass any version check), same `board`/`chip`/`model` as the official,
correct MD5 and no signature. On boot the kernel carries its initramfs inside:
it does not need the rest of the rootfs to give a shell.

## 3. Safe two-step procedure

**Step 1 — validate the container with no risk.** Upload
`ED500-stock-reconstruido.y3` via the web (JUCI → Firmware) or via U-Boot:

```
setenv serverip <IP of your PC>
# copy the file into your TFTP folder named last.y3
run update_image
```

Since its contents are identical to the official firmware, if the router
reboots normally we know our container passes the update. If anything goes
wrong here we lose nothing: it is the same firmware it already had.

**Step 2 — our kernel.** Repeat with `ED500-nuestro-kernel.y3`. If the loader
reads the kernel from a file inside the rootfs (as the official firmware
suggests by shipping a `uImage` inside the UBIFS), it will boot our 5.6.3 and
you will see the banner on `ttyLTQ0`.

## 4. What I still do not know and need from the router

Genexis' U-Boot is custom (`primary system is 1`, `run update_image`,
`Type run flash_nfs…`). Its environment defines **how** the kernel is loaded
(which volume, which path, which address). That is not in any public file: it
must be read from the device with:

```
printenv
```

What I look for: the definition of `update_image` and `bootcmd` (lines with
`ubifsload`, `ubi write`, `bootm`, `rootfs_0`/`rootfs_1`). That is why the
rootfs I built carries the kernel on three plausible paths (`/boot/uImage`,
`/uImage`, `/kernel`); with `printenv` I will leave it on the exact path.

## 5. If it goes wrong

The device has two banks (`rootfs_0` / `rootfs_1`) and a boot counter: a broken
rootfs does not erase the other. And in the worst case there is ROM mode over
UART (bridge the two contacts + load U-Boot into RAM), documented in the repo
`biielfont/Genexis-Pure-ED500/uboot/`.

Before flashing: **disconnect the WAN**. If the router boots and sees TR-069, the
ISP may rewrite the firmware on its own.

## 6. Honest note about "ending up on MikroTik"

The `.y3` solves *how to install*: an unsigned container the router accepts.
What it does not solve is *what to install*. RouterOS has no support for the
GRX350: the mipsbe `.npk` are for MikroTik boards and their userland ships no
drivers for this SoC (neither NAND, nor switch, nor PHY). Even if the kernel
booted with `board=norrland`, RouterOS would be left with no network and no
flash.

What is realistic, and what we are building: **Linux/OpenWrt running on the
ED500**, installable from the web with this `.y3`. If the final goal is
"RouterOS or nothing", the bottleneck is not booting but that MikroTik never
wrote drivers for this chip.

## 7. Headless mode (no serial cable)

The initramfs brings up network and servers on its own:

- requests an IP via **DHCP**; if no lease in 8 s, sets **192.168.1.2/24**
  with gateway 192.168.1.1,
- starts **httpd on port 80** with a status page,
- **telnetd on 23** (root, no password) and **SSH on 22** if dropbear compiled,
- and leaves the shell on `ttyLTQ0` as always.

The page (`http://<ip>/`) refreshes itself every 5 s and the CGI
`/cgi-bin/status` returns plain text with: host, kernel, uptime, a list of
checks (`[ok] kernel`, `[ok] proc`, `[ok] cpus`, `[ok] memory`, `[ok] network
eth0 …`), memory, interfaces and the last 60 lines of `dmesg`.

Tested in QEMU with a real emulated `e1000` NIC:

```
network: 10.0.2.15 on eth0
web: http://10.0.2.15/
telnet: port 23 (root, no password)

=== STATUS ===
[ok] kernel running
[ok] proc mounted
[ok] cpus detected
[ok] memory: 246 MiB
[ok] network eth0 10.0.2.15/24
```

**What is missing on the real ED500:** the kernel already carries the network
stack (`CONFIG_NET`, `INET`, `PACKET`, DHCP), but **there is no Ethernet driver
for the GRX500**. The SoC switch (`GRX500-Switch` in U-Boot) needs the
CBM/DQM + switch driver, which is exactly block H2c. Without it no `eth0`
appears, the initramfs says so on console (`network: no interfaces`) and there
is no page to visit: on hardware, today, the only output is the serial cable.

When that driver lands, this `.y3` already carries the headless image inside:
flash it and the page appears with nothing else to touch.

## 8. 6.18 base with Ethernet (under test)

`out/ED500-net618.y3` (34.5 MB) is the first container with a kernel that
**does ship an Ethernet driver**: the 6.18 tree by grische
(`intel-mips-xrx500-v6.18`), the one that works on the FRITZ!Box 7560 with
this same GRX350.

What it carries inside, verified against the binary:

- `CONFIG_INTEL_XRX500_NET=y`, `INTEL_XRX500_BM=y` → CBM/FSQM, TMU, HDMA and
  the CPU conduit compiled and linked (3 probe symbols present).
- DTB `norrland` **embedded** in section `.dtb.init.rodata`
  (`__dtb_start=0x81390960`, `__dtb_end=0x81392ca8`, 9032 bytes): Genexis'
  U-Boot passes no DTB, so `prom.c` uses `__dtb_start`.
- Headless initramfs (DHCP/fixed IP + status web + telnet).
- `uImage` with `-a 0x80500000 -e 0x8107484c` (ELF entry).

What I **cannot** guarantee: it has never been booted. The DTS is minimal (SoC
+ memory and console); the board parts its drivers expect — reserved memory for
the GPHY firmware, port numbering, PHY addresses, LEDs — are in
`seale_avm.dtsi` for the FRITZ and do not exist here. If the switch does not
find its GPHY firmware, `eth0` will not appear even though the driver is
compiled.

Recommended test order: `ED500-stock-reconstruido.y3` (zero risk) →
`ED500-net618.y3` → and if it does not come back, the other bank boots stock
on its own.
