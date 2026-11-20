# NAND, UBI, and the root filesystem

The ED500 uses a Macronix MX30LF1G18AC NAND device: 128 MiB SLC, 2 KiB pages,
64-byte OOB, and 128 KiB physical eraseblocks (PEBs). The current workflow
reads NAND; it does not install firmware or write NAND.

## Geometry and ECC

| Property | Value |
|---|---|
| Capacity | 128 MiB (1 Gbit) |
| Page size | 2 KiB |
| OOB size | 64 B |
| PEB | 128 KiB |
| UBI LEB | 124 KiB (`126976`) |
| ECC | BCH-4 |
| Bad-block table | `nand-on-flash-bbt` |

The stock Genexis UBI was written with BCH-4. BCH-8 cannot read its EC/VID
headers. The DTB must include:

```text
nand-ecc-strength = <0x04>;
nand-on-flash-bbt;
```

The boot arguments must include:

```text
ubi.mtd=ubi
```

`build-563.sh` checks these settings before packaging the image.

## Partitions

| MTD | Name | Size | Use |
|---|---|---:|---|
| `mtd0` | `uboot` | 1 MiB | U-Boot; read only |
| `mtd1` | `ubi` | 127 MiB | UBI containing firmware/rootfs |

The initramfs attempts to mount `rootfs_0` and `rootfs_1` read-only under
`/newroot/merged/mnt/`. If `ubi.mtd=ubi` is absent, its fallback attaches MTD 1
as UBI device 0.

`mtdblock0` is a raw view of NAND; it is not the `/dev/flash` device expected
by RouterOS. `flash.ko` registers its own character device. Do not create a
manual symlink to `/dev/mtdblock0`.

## Read-only checks

From the initramfs or inspection shell:

```sh
cat /proc/mtd
ls -l /dev/mtd* /dev/mtdblock* /dev/ubi* 2>/dev/null
ubiattach -m 1 -d 0
for d in /sys/class/ubi/ubi0_*; do
  [ -r "$d/name" ] && echo "$(basename "$d"): $(cat "$d/name")"
done
mkdir -p /mnt/rootfs_0
mount -t ubifs -o ro ubi0:rootfs_0 /mnt/rootfs_0
ls /mnt/rootfs_0 | head
```

The stock UBI has several volumes, including `rootfs_0` and `rootfs_1`. Do not
assume volume indices are the same on every device; inspect
`/sys/class/ubi`.

## Verified and unverified

- **Verified:** chip detection, BBT at pages 65472/65408, UBI attach, and
  read-only access to the stock root filesystem.
- **Not verified:** NAND writes, persistent installation, or recovery after a
  write. TFTP boot does not write NAND.
- **RouterOS status:** `getHardwareID` cannot obtain the expected disk identity
  from `/dev/mtdblock0`; the ED500 NAND contains Genexis/Adamo firmware. The
  observed result is `Demo license expired!`.

## Persistent installation

Persistent installation has not been tested. It would require a verified full
backup, a confirmed partition/UBI map, a compatible image, and a recovery plan.
The `.y3` research status is summarized in [FLASH-Y3.md](FLASH-Y3.md); the
current workflow is TFTP to RAM.
