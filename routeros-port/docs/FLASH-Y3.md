# `.y3` format investigation

> **Historical and experimental.** No `.y3` image has been installed on
> hardware. The supported project workflow is TFTP to RAM
> ([BOOT-TFTP.md](BOOT-TFTP.md)); NAND writes are not part of the current
> workflow.

The project examined the ED500 update-container format to understand its
structure. This document intentionally does not provide instructions for
building, signing, or installing modified update images.

## Findings

- The examined vendor image contains a text header, a UBIFS root filesystem,
  package metadata, and an integrity field.
- The examined image did not contain a cryptographic signature field. This
  observation is limited to that sample and is not an endorsement or guide to
  bypassing the device's update controls.
- The format research does not establish that a modified image is safe to
  install, compatible with the bootloader, or recoverable.
- No NAND write or persistent installation has been verified on hardware.

The historical inspection utility is `08-y3tool.py`. Treat its output as
research data, not as evidence that an image is suitable for installation.

## Current project status

The maintained port boots a kernel to RAM over TFTP. It does not install a
modified `.y3` image and does not write NAND. The ED500's NAND geometry and
read-only UBI checks are documented in [NAND-UBI.md](NAND-UBI.md).

RouterOS licensing is a separate issue from the update-container format.
RouterOS must be used with a valid license for the hardware. This repository
does not provide license patches, key generators, or license-bypass
instructions.

## Safety boundary

Do not use this historical research as a flashing procedure. A malformed image
or an incorrect write can make the device unbootable. Any separately
authorized, vendor-supported recovery or update process should be followed
instead.
