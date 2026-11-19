# Troubleshooting

Check the boot chain in order: **console → U-Boot → TFTP → kernel → NAND/UBI →
root filesystem → RouterOS**. Start with the last message that appeared; the
visible failure may be downstream of the cause.

## Console and U-Boot

| Symptom | Likely cause | Check |
|---|---|---|
| No console output | Wrong port or baud rate, cable, or power | Set `ED500_PORT`, use 115200 8N1, and look for `ROM VER` at power-on |
| `ROM VER` repeats | Wrong image entry point | Use `out/uImage-563` with load/entry `0x80500000` |
| U-Boot prompt is not caught | Autoboot starts before the carriage return is sent | Start the catcher before power-on |
| `Bad Magic Number` | ELF or corrupt file was loaded | Load `uImage-563` with `bootm` |
| `COM4 busy` | Another process has the serial port | Close the other console or TFTP utility |

The catcher sets `ipaddr` and `serverip`. For a different PC network, pass
`--pc-ip` and ensure U-Boot is configured for the same subnet.

## TFTP

| Symptom | Likely cause | Check |
|---|---|---|
| TFTP timeout | Firewall, wrong IP, or occupied port | Allow Python on the private network; check port 69/6969 and `tftpdstp` |
| Transferred size differs | The image changed during transfer | Stop the catcher and retry with a stable image |
| Retry limit exceeded | No PC-to-device route | Use the same LAN and check the PC IP and cable |
| Transfer size is zero | Catcher was started from the wrong directory | Run it from `routeros-port`; it serves `out/` |

## Kernel

| Symptom | Likely cause | Check |
|---|---|---|
| No `Linux version` message | Silent `bootm`, wrong entry point, or truncated image | Verify `uImage-563` and the TFTP log |
| Hang after `MIPS: machine is...` | Clock or GIC configuration issue | Review the DTB and use a previously verified image |
| Panic during rootfs startup | Init, overlay, or UBI issue | Check the console and `dmesg` |
| `Attempted to kill init` | The inspection shell exited while running as PID 1 | Do not use `switch_root` with a shell as init |

## NAND and UBI

| Symptom | Likely cause | Check |
|---|---|---|
| `No such device` mounting `ubi0:rootfs_0` | UBI is not attached or the volume is absent | Check `/proc/mtd`, attach UBI as documented, and inspect `/sys/class/ubi` |
| `ecc unrecoverable error` | ECC setting differs from the stock UBI | Use BCH-4 and check the DTB and boot arguments |
| No `/dev/mtd*` | NAND driver did not probe or the DTB is wrong | Check `dmesg` and the NAND driver configuration |
| No bad-block-table message | BBT option is missing or the chip was not detected | Check the DTB; do not force a BBT write |
| UBIFS mount reports `invalid argument` | Geometry, ECC, or volume mismatch | Do not write; verify PEB/LEB and the volume |

See [NAND-UBI.md](NAND-UBI.md) for geometry and read-only checks.

## RouterOS

| Symptom | Likely cause | Check |
|---|---|---|
| `Unknown symbol` loading `packet_hook`, `switch`, or `bridge2` | RouterOS modules depend on unavailable MikroTik fastpath symbols | This is not fixed by another `insmod`; no proprietary binaries are included |
| `phy_helper: Unknown symbol ...` | Module depends on symbols not exported by this kernel | Record the diagnostic; do not treat it as a configuration issue |
| `getHardwareID: could not get disk /dev/mtdblock0` / `Demo license expired!` | RouterOS cannot obtain the expected disk identity | The current NAND contains Genexis/Adamo firmware |
| `applet not found` in the inspection shell | BusyBox applet lookup uses `argv[0]` | Invoke the `busybox` binary directly |
| Overlay reports missing xattrs | Upper layer is tmpfs without xattr support | Informational; some overlay features are unavailable |

Linux Ethernet support does not make RouterOS networking functional. RouterOS
modules still require their own compatible network components.

## Build

| Symptom | Likely cause | Check |
|---|---|---|
| `build-563.sh` fails in `olddefconfig` | Missing dependency or incomplete source tree | Review `/opt/olddef.log` and run bootstrap steps `01`–`04` |
| `CONFIG FALLO` (literal script output) | Option is absent from this kernel tree | Review the error; do not disable checks blindly |
| DTB lacks BCH-4 | Boot patch was not applied or DTB is stale | Rebuild and inspect the generated DTB |
| `mkimage` fails | `u-boot-tools` is missing | Install the package using the system package manager |
| Rootfs check fails | `ros/rootfs.squashfs` is absent | Follow [BUILD.md](BUILD.md) and use a lawfully obtained package |
| Wrong endianness | Little-endian target was built | The target userland is `mipsbe` |

## Recovery

- If TFTP boot fails, power-cycle the device without the catcher; the stock
  firmware remains in NAND.
- Do not write NAND to troubleshoot a RAM boot failure.
- Save relevant logs before requesting help, but redact IPs, MACs, and serial
  numbers.
