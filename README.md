# Genexis Pure ED500 — RouterOS 7.17 research port

Research port of **RouterOS 7.17 mipsbe** to the **Genexis Pure ED500**
(Intel/Lantiq **GRX350**, big-endian MIPS interAptiv), booted over TFTP to RAM
without writing flash.

[Progress](PROGRESS.md) · [Documentation](routeros-port/docs/README.md) ·
[Progress map](routeros-port/progress.svg) ·
[Contributing](routeros-port/CONTRIBUTING.md)

> **Independent project; no MikroTik software is included.** This project is
> not affiliated with MikroTik, Genexis, or Intel/Lantiq. RouterOS packages and
> root filesystems must be obtained separately under MikroTik's terms. This
> repository does not provide license patches, key generators, or license
> bypasses.

## Current status

![Progress map](routeros-port/progress.svg)

**60% complete (60/100 weighted points).** The map is generated from
version-controlled data and is embedded here and in [PROGRESS.md](PROGRESS.md).

| Area | Weight | Complete | Status |
|---|---:|---:|---|
| Boot and platform | 20 | 20 | Verified |
| Ethernet/switch/PHY in Linux | 10 | 10 | Verified |
| NAND/UBI/UBIFS read-only | 10 | 10 | Verified |
| RouterOS rootfs/overlay/shell | 10 | 10 | Verified |
| RouterOS modules | 10 | 3 | Partial |
| Networking in RouterOS | 20 | 1 | Blocked |
| RouterOS license | 10 | 0 | Blocked |
| Persistent installation/`.y3` | 5 | 1 | Partial |
| Remote tools and documentation | 5 | 5 | Verified |
| **Total** | **100** | **60** | **60%** |

### Verified on hardware

- MikroTik Linux 5.6.3 kernel for `mipsbe`, built for the GRX350.
- TFTP-to-RAM boot and `ttyLTQ0` console at 115200 baud.
- 1 Gbps Ethernet in Linux using DSA, GSWIP XRX500, and XWAY PHY.
- 128 MiB NAND (Macronix MX30LF1G18AC) with BCH-4 ECC and BBT.
- Read-only UBI/UBIFS mounts for `rootfs_0` and `rootfs_1`.
- RouterOS SquashFS root filesystem, temporary overlay, and inspection shell.
- RouterOS `flash.ko` loaded.

### Known limitations

- RouterOS networking is unavailable. Its modules depend on proprietary
  fastpath symbols and a switch driver for MikroTik hardware.
- RouterOS reports `Demo license expired!`. The documented `getHardwareID`
  failure is that the expected MikroTik disk identity is unavailable from
  `/dev/mtdblock0`; the ED500 NAND contains Genexis/Adamo firmware. The
  repository does not establish a key-generator or NAND-write failure.
- Persistent installation has not been tested. The current workflow boots to
  RAM and does not write NAND.
- The final `out/uImage-563` artifact needs another on-device test; the latest
  recorded tests used earlier builds (#29/#62).

See [PROGRESS.md](PROGRESS.md) for milestones, evidence, and history.

## Project overview

The ED500 uses a dual-core GRX350 SoC, 128 MiB SLC NAND, a GSWIP switch, and
XWAY PHYs. RouterOS 7.17 for `mipsbe` uses Linux 5.6.3, which MikroTik publishes
under its GPL source release. The project reuses that kernel, adds platform
support, and boots a separately obtained RouterOS root filesystem in RAM.

This repository contains research tools, patches, diagnostics, and
documentation. It is not a complete alternative firmware. Linux networking
and RouterOS networking are separate parts of the work.

| Component | Details |
|---|---|
| SoC | Intel/Lantiq GRX350, dual-core big-endian MIPS interAptiv |
| RouterOS kernel | Linux 5.6.3 (`mipsbe`) |
| NAND | Macronix MX30LF1G18AC, 128 MiB SLC |
| ECC/BBT | BCH-4, `nand-on-flash-bbt` |
| Switch | GSWIP XRX500 via DSA (`gswip3`) |
| PHY | XWAY; 1 Gbps link verified |
| Console | `ttyLTQ0`, 115200 8N1 |
| Current boot | TFTP to RAM; NAND is not written |

## Quick start

### Requirements

- Linux or WSL2; scripts use `/opt/ros-port` and `/opt/toolchain`.
- Bootlin MIPS toolchain `mips32--glibc--stable-2024.05-1`.
- Linux 5.6.3 sources, MikroTik GPL patch, and `mips.config`.
- `make`, `bc`, `flex`, `bison`, `libssl-dev`, `libelf-dev`, `xz-utils`,
  `patch`, `wget`, `mkimage` (`u-boot-tools`), `squashfs-tools`, `cpio`,
  `gzip`, `bzip2`, and Python 3.
- An official RouterOS 7.17 `mipsbe` `.npk` from which to extract
  `ros/rootfs.squashfs`. It is not versioned.
- Serial connection at 115200 8N1 (default `COM4`; set `ED500_PORT`) and an
  ED500 LAN connection.

### Prepare and build

```bash
git clone https://github.com/biielfont/genexis-routeros-port.git
cd genexis-routeros-port/routeros-port
python3 -m pip install -r requirements.txt
```

Place the lawfully obtained root filesystem at `ros/rootfs.squashfs`. The
`.gitignore` excludes `ros/`, `out/`, and `logs/`; do not commit them.

See [docs/BUILD.md](routeros-port/docs/BUILD.md) for the full bootstrap. If
`/opt/ros-port/linux-5.6.3` is already prepared:

```bash
sudo bash build-563.sh
```

The expected output is `out/uImage-563`, with load and entry address
`0x80500000`. The build checks the BCH-4 DTB settings, `nand-on-flash-bbt`,
`ubi.mtd=ubi`, and inclusion of the RouterOS root filesystem.

### Boot over TFTP

```bash
python catch_final.py --horas 6
# On Windows, double-click ARRANCAR-563.bat
```

The catcher serves `out/uImage-563` over TFTP, waits for the U-Boot prompt,
downloads the image, and runs `bootm`. **The image is loaded into RAM; NAND is
not written.** See [BOOT-TFTP.md](routeros-port/docs/BOOT-TFTP.md) for manual
commands and troubleshooting.

### Remote reset

```bash
python uboot_cycle.py status
python uboot_cycle.py cycle
python uboot_cycle.py watch --horas 6
```

`uboot_cycle.py` can reset through U-Boot or the RCU register and reload the
image without cutting power or writing NAND.

## Repository layout

```text
README.md                  # project overview
PROGRESS.md                # milestones and evidence
routeros-port/             # port code, patches, and documentation
  progress.svg             # generated progress map
  progress.json            # milestone data
  tools/progress.py        # SVG generator
  README.md                # technical guide
  build-563.sh             # current build
  init-initramfs.sh        # initramfs setup
  catch_final.py           # U-Boot catcher and TFTP
  uboot_cycle.py           # remote reset and boot
  docs/                    # current guides and history
  refs/, tree/             # reference DTS and platform patches
```

`routeros-port/ros/`, `routeros-port/out/`, and `routeros-port/logs/` are not
versioned. Root-level historical logs may contain network data; sanitize them
before reuse. Do not add IP addresses, MAC addresses, or serial numbers.

## Verification

Regenerate the progress map from its source data:

```bash
cd routeros-port
python3 tools/progress.py
```

The current reference artifact is `out/uImage-563` (19,672,756 bytes,
MD5 `1a780fdd76b9da701974b17af1102be6`, load/entry `0x80500000`). The artifact
has not been retested on hardware after the latest reorganization. Do not
describe it as verified until the exact image has been booted and checked.

## Legal and safety scope

- RouterOS, `.npk` files, root filesystems, and NAND dumps are not included or
  redistributed.
- No license patch, key generator, or license bypass is provided.
- The default boot path is RAM/TFTP. Do not write to NAND without a verified
  backup and a recovery plan.
- Sanitize logs before attaching them to issues.
- Kernel sources and MikroTik patches have their own licenses; see
  [routeros-port/NOTICE.md](routeros-port/NOTICE.md).

Contributions to documentation, reproducibility, diagnostics, and original
drivers are welcome. Read
[routeros-port/CONTRIBUTING.md](routeros-port/CONTRIBUTING.md) first.
