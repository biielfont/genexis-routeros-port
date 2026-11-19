# Historical notes: GSWIP XRX500 port to Linux 5.6.3

> **Historical note (November 2026).** These notes capture an earlier driver
> porting effort and may not reflect the current tree. See
> [BUILD.md](../BUILD.md) and the [current progress report](../PROGRESS.md).

## Background

RouterOS 7.17 `mipsbe` uses Linux 5.6.3. The MikroTik GPL source release
provided the base kernel. At the time these notes were written, the kernel
contained generic Lantiq GSWIP support but not the XRX500 driver needed by the
ED500.

## Porting work recorded

The effort adapted XRX500 DSA code from a newer kernel and added a compatibility
layer for APIs that differ between kernel 5.6.3 and 6.x. Differences included
DSA port helpers, phylink callbacks, ethtool statistics, VLAN callbacks,
regmap access, and the GSWIP3 tag protocol.

The early strategy was to target a minimal switch configuration first and defer
advanced bridge offload, statistics, mirroring, and VLAN filtering.

## Historical build status

The notes recorded repeated reductions in compiler errors and a remaining set
of API mismatches around regmap, ethtool, phylink, and DSA. Those counts and
script names are historical, not a current build-status report.

The current documented hardware status is Linux Ethernet through
DSA/GSWIP/XWAY PHY at 1 Gbps. RouterOS networking remains a separate blocker:
its modules depend on unavailable MikroTik fastpath symbols.

## References

For maintained build instructions, see [BUILD.md](../BUILD.md). For current
hardware status and limitations, see [PROGRESS.md](../PROGRESS.md).
