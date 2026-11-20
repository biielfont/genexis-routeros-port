# `.y3` format investigation

> **Historical and experimental.** No `.y3` image has been installed on
> hardware. The supported project workflow is TFTP to RAM
> ([BOOT-TFTP.md](BOOT-TFTP.md)); NAND writes are not part of the current
> workflow.

The project examined the ED500 update-container format to understand its
structure.

## Findings

- The examined vendor image contains a text header, a UBIFS root filesystem,
  package metadata, and an integrity field.
- The examined image did not contain a cryptographic signature field. This
  observation is limited to that sample.
- The format research does not establish that a modified image is safe to
  install, compatible with the bootloader, or recoverable.

The historical inspection utility is `08-y3tool.py`. Treat its output as
research data, not as evidence that an image is suitable for installation.

## Current project status

The maintained port boots a kernel to RAM over TFTP. It does not install a
modified `.y3` image or write NAND. The ED500's NAND geometry and read-only UBI
checks are documented in [NAND-UBI.md](NAND-UBI.md).
