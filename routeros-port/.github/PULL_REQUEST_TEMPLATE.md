## What changed

<!-- Briefly describe the change and link an issue if applicable. -->

## Why

<!-- Describe the problem and how you verified the change. -->

## Tests

- [ ] `sudo bash build-563.sh` (if kernel or initramfs changes)
- [ ] TFTP boot on hardware (if kernel or initramfs changes)
- [ ] `python3 tools/progress.py` (if `progress.json` changes)
- [ ] Documentation links reviewed

## Legal and security checklist

- [ ] No `.npk`, rootfs, NAND dumps, or proprietary software included.
- [ ] No credentials, IP addresses, MAC addresses, or serial numbers included.
- [ ] NAND-related changes explain backup, geometry, and recovery plans.

## Not tested

<!-- State clearly what you could not test. -->
