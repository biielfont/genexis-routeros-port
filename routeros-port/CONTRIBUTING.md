# Contributing

Thanks for your interest. This is a hardware research project. The priorities
are to avoid damaging devices and to make results reproducible.

## Scope

Contributions are welcome for:

- Documentation and command corrections.
- Reproducible builds, dependencies, and portable scripts.
- Diagnostics for NAND/UBI, switch, PHY, console, or boot.
- Original drivers and compatible GPL patches.
- Hardware tests with sanitized logs.

Do not submit:

- `.npk` files, root filesystems, NAND dumps, proprietary firmware, or other
  MikroTik or Genexis software.
- Credentials, public IP addresses, MAC addresses, serial numbers, or personal
  backups.

## Before working on hardware

- The default method is TFTP to RAM. Do not write to NAND.
- NAND/UBI changes require a backup, verified geometry, and a recovery plan.
- Test on your own device and record the board revision, U-Boot version, and
  sanitized logs.
- Do not publish a `.y3` or `uImage` containing a RouterOS root filesystem.

## Workflow

1. Open an issue using the hardware or bug template before a large change.
2. Create a descriptive branch, such as `docs/...`, `fix/...`, or `feat/...`.
3. Keep changes focused and explainable; avoid unnecessary whole-file
   reformatting.
4. For kernel or initramfs changes, run the build and record the result:
   ```bash
   sudo bash build-563.sh
   md5sum out/uImage-563
   ```
5. For documentation changes, check relative links. If a milestone changes,
   update `progress.json` and regenerate the SVG:
   ```bash
   python3 tools/progress.py
   ```
6. Open a PR using the template and identify anything you could not test.

## Style

- Write documentation in English.
- Follow the style of the existing scripts and avoid dependencies when the
  standard library is sufficient.
- Do not hard-code machine-specific absolute paths in new scripts. Use a
  path relative to the script or an environment variable.
- Do not commit logs, `out/`, `ros/`, or `__pycache__/`.

## Pull request checklist

- [ ] The change has a clear, limited purpose.
- [ ] It includes no proprietary software, rootfs, `.npk`, or NAND dumps.
- [ ] It includes no credentials or personal/network identifiers.
- [ ] `build-563.sh` still works, if applicable.
- [ ] Related documentation is updated.
- [ ] `progress.json` and `progress.svg` are synchronized, if applicable.
- [ ] Untested areas are stated explicitly.
