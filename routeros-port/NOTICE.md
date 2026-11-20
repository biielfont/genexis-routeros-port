# Legal notice

This is an independent research project. It is not affiliated with, sponsored
by, or endorsed by MikroTik, Genexis, or Intel/Lantiq. Product names and
trademarks belong to their respective owners.

## Third-party software

- RouterOS and `.npk` files are proprietary MikroTik software. They are not
  included or redistributed in this repository. Obtain them from MikroTik
  under its terms and license.
- The RouterOS root filesystem is also excluded. `ros/` is ignored by Git.
- The Linux 5.6.3 kernel and MikroTik GPL patch are obtained from published
  sources. They retain their respective licenses (the kernel is GPL-2.0; see
  the source tree's `COPYING` files). This repository's patches do not change
  those licenses.
- U-Boot, BusyBox, Dropbear, and system tools retain their original licenses.

## This repository

There is no `LICENSE` file because the repository combines original scripts,
patches derived from a GPL kernel, and documentation. No implicit license is
granted for original code beyond what applicable law permits. Before
redistribution, the maintainer should choose a license and review GPL-2.0
compatibility.

## RouterOS licensing

The current ED500 test reports `Demo license expired!`. This status is separate
from the kernel, NAND-read, and boot results described elsewhere.

## Security

Do not publish logs containing IP addresses, MAC addresses, serial numbers,
keys, NAND backups, or other network data. Do not write to NAND without a
verified backup and a recovery plan.
