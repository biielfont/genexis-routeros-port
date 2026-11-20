# Boot to RAM over TFTP

The current project workflow boots `uImage-563` to RAM using U-Boot and TFTP.
The kernel starts its initramfs and mounts the RouterOS root filesystem with a
temporary overlay. **This workflow does not write to NAND.** Without the TFTP
catcher, the ED500 boots its original firmware.

## Requirements

- ED500 with U-Boot prompt `IOPSYS 2 grx500 #`.
- Serial console at 115200 8N1. Scripts default to `COM4`; set `ED500_PORT` if
  needed.
- PC and ED500 on the same LAN. Defaults are PC `192.168.1.161` and U-Boot
  `192.168.1.1`; `catch_final.py` can detect the PC address if `--pc-ip` is
  omitted.
- `out/uImage-563` built by `build-563.sh`.
- Python 3 and `pyserial` (`python3 -m pip install -r requirements.txt`).

## Automatic catcher

Run from the repository root on Windows or Linux:

```bash
python catch_final.py --horas 6
```

The script starts a TFTP server on port 69 or, if occupied, port 6969; waits
for the U-Boot prompt; sets the network parameters; downloads `uImage-563` to
`0x80500000`; checks the transferred size; and runs `bootm`. The log is written
to `logs/try563_v2.log`.

By default, the script releases COM4 45 seconds after `bootm`. Use `--seguir`
to keep monitoring and re-arm the boot. Set the PC address explicitly with
`--pc-ip`. On Windows, `ARRANCAR-563.bat` starts the same workflow.

## Manual U-Boot boot

At the U-Boot prompt:

```text
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.161
setenv tftpdstp 69
tftpboot 0x80500000 uImage-563
bootm 0x80500000
```

The image is packaged for `0x80500000`. Do not use `0x82000000` unless booting
a different image. If the TFTP server uses port 6969, set `tftpdstp` to 6969
and check that the PC firewall permits the transfer.

## Expected output

The console should show the kernel booting, the GSWIP switch probe, and the
RouterOS root filesystem reaching the `~ #` inspection shell. This is not the
full RouterOS CLI. RouterOS networking remains unavailable because required
network components are missing.

## Remote reset

`uboot_cycle.py` can inspect status, reset to U-Boot, boot the image, or repeat
the TFTP boot cycle:

```bash
python uboot_cycle.py status
python uboot_cycle.py reset
python uboot_cycle.py boot
python uboot_cycle.py cycle
python uboot_cycle.py watch --horas 6
```

The Linux reset path uses the RCU reset register through `/dev/mem`; it does not
write to NAND. A failed reset can leave the board halted and may require a
power cycle.

## Common problems

| Symptom | Check |
|---|---|
| No console output | `ED500_PORT`, 115200 8N1, cable, and power |
| `ROM VER` repeats | Correct image and entry point (`0x80500000`) |
| TFTP does not transfer | PC IP, firewall, port 69/6969, and `tftpdstp` |
| Transferred size differs | The image may have changed during transfer |
| `Bad Magic Number` | Use a valid `uImage-563` with `bootm` |
| No `lan*` interfaces | Check switch/PHY probe messages in `dmesg` |
| `Demo license expired` | License status, not a boot failure |

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and
[NAND-UBI.md](NAND-UBI.md).
