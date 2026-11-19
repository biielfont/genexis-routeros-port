# Documentation

The project entry point is the [repository README](../README.md). This folder
separates current guides from historical research notes.

## Current guides

| Document | Purpose |
|---|---|
| [BUILD.md](BUILD.md) | Prepare the toolchain and sources, build, and verify `out/uImage-563` |
| [BOOT-TFTP.md](BOOT-TFTP.md) | Boot to RAM over TFTP, catch U-Boot, and reset remotely |
| [NAND-UBI.md](NAND-UBI.md) | NAND geometry, BCH-4/BBT, UBI attach, and read-only mounts |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common failures and diagnostic checks |
| [PROGRESS.md](PROGRESS.md) | Progress map and milestone status |
| [FLASH-Y3.md](FLASH-Y3.md) | Non-operational summary of the experimental `.y3` investigation |

## Progress map

The graphic is [../progress.svg](../progress.svg), embedded in the
[repository README](../README.md) and [PROGRESS.md](PROGRESS.md). It is
generated from `progress.json` by `tools/progress.py`; there is no separate
HTML page or manually maintained graphic.

## Historical notes

These files are retained as a record of earlier research. They may describe
outdated paths or conclusions:

- [history/CHECKLIST-2026-11.md](history/CHECKLIST-2026-11.md) — initial boot
  checklist and earlier audit.
- [history/NOTES-5.6.3-port.md](history/NOTES-5.6.3-port.md) — GSWIP driver
  port notes and build errors.

## Documentation guidelines

- Commands should work when copied from the repository root.
- Machine-specific absolute paths should not be needed to understand a
  procedure; document them as historical when a script requires them.
- Do not commit logs, root filesystems, `.npk` files, or `out/` artifacts.
- When a milestone changes, update `progress.json` and regenerate
  `progress.svg` with `python3 tools/progress.py`.
