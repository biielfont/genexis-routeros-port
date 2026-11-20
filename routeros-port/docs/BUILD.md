# Build the kernel and `uImage`

This guide covers the current build path, `build-563.sh`. Scripts `01`–`04`
bootstrap the kernel tree and initramfs; scripts `05`/`06` and older
`patch_*`/`check_*` scripts are historical.

## Supported environment

- Linux x86_64 or WSL2. Scripts use `/opt/ros-port` and `/opt/toolchain`.
- A user with permission to write under `/opt`, or `sudo`.
- Python 3.8 or newer.
- QEMU is not needed for the ED500 TFTP workflow.

On Debian/Ubuntu/Kali:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  make bc flex bison libssl-dev libelf-dev xz-utils patch wget \
  ca-certificates u-boot-tools squashfs-tools cpio gzip bzip2 python3-pip
```

`u-boot-tools` provides `mkimage`; `squashfs-tools` provides `unsquashfs` and
`mksquashfs`.

## 1. Bootstrap the 5.6.3 tree

From the repository root:

```bash
sudo bash 01-build-gpl-kernel.sh
sudo bash 02-apply-platform.sh
sudo bash 03-build-intel-mips.sh
sudo bash 04-build-initramfs.sh
```

| Script | Purpose |
|---|---|
| `01-build-gpl-kernel.sh` | Downloads the Bootlin toolchain, Linux 5.6.3, the MikroTik GPL patch, and `mips.config`; applies the patch and builds a reference kernel |
| `02-apply-platform.sh` | Adds the platform files and connects them to Kconfig/Kbuild |
| `03-build-intel-mips.sh` | Builds the minimal platform and writes `/opt/ros-port/build4.log` |
| `04-build-initramfs.sh` | Builds static MIPS big-endian BusyBox and a base rescue initramfs |

The current build expects:

```text
/opt/toolchain/bin/mips-buildroot-linux-gnu-*
/opt/ros-port/linux-5.6.3/
/opt/ros-port/initramfs/
/opt/ros-port/fw/lantiq/xrx500-phy-fw.bin
```

The kernel source tree is not included in this repository. The GPL patch and
`mips.config` are obtained from MikroTik's published GPL sources; the mirror
used by script `01` is
[`tikoci/mikrotik-gpl`](https://github.com/tikoci/mikrotik-gpl).

## 2. RouterOS root filesystem

The root filesystem is not redistributed. Obtain an official RouterOS 7.17
`mipsbe` package from MikroTik and extract `rootfs.squashfs` using an
appropriate package-inspection tool. Place it at:

```text
ros/rootfs.squashfs
```

The `.gitignore` excludes `ros/*.npk`, `ros/*.squashfs`, and `ros/rootfs/`. Do
not commit or redistribute those files.

## 3. Current build

```bash
sudo bash build-563.sh
```

The script applies `parche_arranque.py`, prepares the initramfs, compiles the
diagnostic utilities, enables required kernel options, builds `vmlinux`,
validates the DTB, and packages `out/uImage-563` for `0x80500000`.

Minimum checks:

```bash
ls -l out/uImage-563
md5sum out/uImage-563
/opt/toolchain/bin/mips-buildroot-linux-gnu-readelf -h \
  /opt/ros-port/linux-5.6.3/vmlinux | grep -E 'Data|Entry'
```

The build checks for:

- DTB `nand-ecc-strength = <4>` and `nand-on-flash-bbt`.
- `ubi.mtd=ubi` in the boot arguments.
- RouterOS rootfs present in the initramfs.
- Load and entry addresses at `0x80500000`.
- Big-endian MIPS output (`mipsbe`).

The reference `uImage-563` measured 19,672,756 bytes and had MD5
`1a780fdd76b9da701974b17af1102be6`. Output size changes with the initramfs,
rootfs, or configuration.

## 4. Reproducibility notes

- `build-563.sh` resolves its own directory, so it can be invoked from another
  working directory.
- Scripts `02`, `04`, `05`, and `06` also resolve their own paths. Scripts
  `01` and the kernel tree intentionally use `/opt/ros-port`.
- The build is not hermetic: it downloads the toolchain and source and uses the
  rootfs supplied under `ros/`. Record the package, GPL patch, and toolchain
  versions when reproducing a build.
- The latest recorded hardware test predates the final artifact. Retest each
  changed image before describing it as hardware-verified.

Next: [BOOT-TFTP.md](BOOT-TFTP.md).
