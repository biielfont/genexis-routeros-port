# Security

## What to report

- A defect that could prevent the device from booting, such as an unsafe NAND
  write or a failed reset.
- Exposed credentials, keys, personal logs, or backups.

## How to report

Do not open a public issue containing sensitive data. Contact the repository
maintainer privately or use a GitHub security advisory if available. Include:

- Repository version or commit.
- Device model and board revision.
- Minimal reproduction steps.
- A sanitized log.
- Impact and whether recovery was tested.

## Do not publish

- Public IP addresses, MAC addresses, serial numbers, or keys.
- NAND dumps, `.npk` files, root filesystems, or `.y3` files containing
  proprietary content.
- RouterOS, Wi-Fi, or ISP credentials.
- Unsanitized full logs.

## Project scope

The default boot method is TFTP to RAM and does not write to NAND. Contributions
that change this behavior must document the risks, backup, and recovery plan
before review.
