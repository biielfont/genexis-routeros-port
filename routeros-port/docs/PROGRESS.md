# Port status

![Progress map](../progress.svg)

**60% complete (60/100 weighted points).** Last updated: **2026-11-19**.
The map is generated from [`progress.json`](../progress.json) by
[`tools/progress.py`](../tools/progress.py).

The percentage reflects engineering milestones, not overall RouterOS
usability. RouterOS and its root filesystem are MikroTik software; this
repository does not redistribute them or bypass licensing.

## Summary

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

## Verified

- Linux 5.6.3 for `mipsbe` boots on the GRX350 over TFTP to RAM.
- Serial console works on `ttyLTQ0` at 115200 8N1.
- Linux Ethernet works through DSA/GSWIP/XWAY PHY at 1 Gbps.
- NAND is detected with BCH-4 ECC and BBT; UBI/UBIFS volumes mount read-only.
- The RouterOS root filesystem reaches an inspection shell with a temporary
  overlay in earlier hardware-tested builds.

## Blocked or unverified

- RouterOS networking requires MikroTik fastpath symbols and compatible
  platform components that are not available in this repository.
- RouterOS reports `Demo license expired!`. `getHardwareID` is documented as
  unable to obtain the expected disk identity from `/dev/mtdblock0`; the NAND
  contains Genexis/Adamo firmware. These documents do not establish that a
  key generator failed to write NAND. The current workflow does not write NAND.
- Persistent installation and recovery have not been tested.
- The final `out/uImage-563` artifact needs another on-device test; previous
  recorded tests used builds #29/#62.

## Update the map

1. Update `percent`, `state`, and `evidence` in [`progress.json`](../progress.json).
2. Run `python3 tools/progress.py` from `routeros-port/`.
3. Review `progress.svg` and the rendered README.
4. Commit `progress.json` and `progress.svg` together.

Do not edit the generated SVG by hand. For milestone details and test
instructions, see the repository's [progress report](../../PROGRESS.md).
