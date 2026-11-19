# Initial 5.6.3 boot checklist

> **Historical note (November 2026).** This checklist records an earlier
> hardware test and audit. Some details are outdated; use
> [BOOT-TFTP.md](../BOOT-TFTP.md) and the [current progress report](../PROGRESS.md)
> for the maintained status.

## Original test setup

- Serial console: COM4, 115200 8N1.
- Ethernet: PC connected to an ED500 LAN port.
- TFTP server: `uImage-563` served from the repository's `out/` directory.
- PC address: `192.168.1.160/24` in the original setup.

The earlier manual U-Boot sequence was:

```text
tftpboot 0x80500000 uImage-563
bootm 0x80500000
```

## Expected boot signs

The checklist expected Linux 5.6.3, the `ttyLTQ0` console, a GSWIP probe, DSA
LAN ports, and the inspection shell. The original notes also described a
headless web/telnet setup; that is historical and is not the maintained boot
procedure.

## Audit notes

The pre-test audit identified kernel configuration and platform issues,
including serial support, bridge configuration, initramfs utilities, GPHY
firmware, GRX500 clocks, and userspace kernel options. The recorded fixes were
included in later builds.

This checklist does not establish that the final `uImage-563` has been tested.
The latest recorded hardware results used earlier builds (#29/#62). No NAND
write was part of the TFTP test.

## Licensing note

The earlier investigation noted that RouterOS may require a license tied to
hardware. This project does not patch licensing or bypass a license check.
