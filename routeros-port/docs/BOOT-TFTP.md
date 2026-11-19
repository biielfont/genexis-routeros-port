# Arranque por TFTP a RAM

Todo el arranque de este repo es **en RAM**: U-Boot carga `uImage-563` por
TFTP, el kernel ejecuta su initramfs y monta el rootfs de RouterOS en un
overlay. **No se escribe NAND**. Si no hay cazador, el ED500 arranca su firmware
original.

## Requisitos

- ED500 con U-Boot `IOPSYS 2 grx500 #`.
- Consola serie a **115200 8N1**. Por defecto los scripts usan `COM4`; define
  `ED500_PORT` si tu puerto es otro.
- PC y ED500 en la misma LAN. Los scripts usan `192.168.1.161` para el PC y
  `192.168.1.1` para U-Boot; `catch_final.py` detecta la IP local si no le pasas
  `--pc-ip`.
- `out/uImage-563` generado por `build-563.sh`.
- Python 3 con `pyserial` (`python3 -m pip install -r requirements.txt`).

## Cazador automático (recomendado)

Desde la raíz del repo, en Windows o Linux:

```bash
python catch_final.py --horas 6
```

El proceso:

1. abre un servidor TFTP en el puerto 69 o, si está ocupado, en 6969;
2. machaca CR en la consola hasta ver `grx500 #`;
3. fija `ipaddr`, `serverip` y `tftpdstp` en U-Boot;
4. ejecuta `tftpboot 0x80500000 uImage-563`;
5. comprueba que los bytes transferidos coinciden con el fichero;
6. ejecuta `bootm 0x80500000` y deja el log en `logs/try563_v2.log`.

Por defecto **libera COM4 a los 45 s** del `bootm` para que puedas usar la
consola. Si quieres que siga vigilando y rearme el arranque, usa `--seguir`.
Puedes forzar la IP del PC con `--pc-ip 192.168.1.161`.

En Windows, `ARRANCAR-563.bat` lanza lo mismo con doble clic.

## Arranque manual desde U-Boot

Si ya estás en el prompt:

```text
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.161
setenv tftpdstp 69
tftpboot 0x80500000 uImage-563
bootm 0x80500000
```

`0x80500000` es la dirección de carga y entrada del `uImage-563` final. No
cargues en `0x82000000` salvo que sepas que estás usando otra imagen: el
`uImage` de este repo está empaquetado para `0x80500000`.

Si el puerto 69 está ocupado, arranca el TFTP en 6969 y pon `tftpdstp 6969`.
Comprueba el firewall de Windows: el TFTP entrante debe llegar al proceso.

## Qué deberías ver

En orden aproximado:

```text
ROM VER: 2.1.0
U-Boot 2016.07-INTEL...
Bad block table found at page 65472, version 0x01
Bad block table found at page 65408, version 0x01
...
Linux version 5.6.3 ...
CPU0 revision is: 0001a120 (MIPS interAptiv (multi))
MIPS: machine is Genexis Pure ED500 (GRX350)
...
gswip-xrx500 1c000000.switch: probed GSWIP version 30 mod 0
...
--- RouterOS: montando rootfs ---
overlay listo, arrancando /sbin/sysinit
...
--- shell dentro de RouterOS ---
~ #
```

El prompt `~ #` es el shell de inspección dentro del rootfs de RouterOS. No es
la CLI completa de RouterOS: `sysinit` y el chequeo de licencia se ejecutan por
detrás, pero la red de RouterOS sigue bloqueada por los módulos del *fastpath*.

## Reinicio remoto

`uboot_cycle.py` hace el ciclo completo sin cortar la corriente:

```bash
python uboot_cycle.py status            # uboot / linux / desconocido
python uboot_cycle.py reset             # reset y quedarse en U-Boot
python uboot_cycle.py boot              # cargar uImage-563 desde U-Boot
python uboot_cycle.py cycle             # reset + catch + TFTP + bootm
python uboot_cycle.py watch --horas 6   # rearma si la placa se reinicia
```

Desde U-Boot usa `reset`. Desde Linux escribe `RCU_RST_REQ` en
`0x16000010`, bit 30 (`0x40000000`), por `/dev/mem`. Es el mismo bit del nodo
`syscon-reboot` del DTS, pero no depende de que el kernel tenga registrado el
handler ni de que el chroot de RouterOS tenga `reboot` en el PATH. Si el reset
fallara, el kernel puede quedarse en `Reboot failed -- System halted`; en remoto
eso deja la placa colgada. El reset por RCU no toca la NAND.

## Problemas típicos

| Síntoma | Qué mirar |
|---|---|
| No aparece nada en consola | COM4/`ED500_PORT`, 115200 8N1, cable, que U-Boot esté vivo |
| `ROM VER` en bucle | La imagen no es para esta placa o la entry no es `0x80500000` |
| TFTP no transfiere | IP del PC, firewall, puerto 69/6969, `tftpdstp` |
| `Bytes transferred` no coincide | El fichero cambió mientras se servía; vuelve a lanzar el cazador |
| `Bad Magic Number` | Estás usando un ELF o una imagen corrupta; usa `uImage-563` |
| Arranca y no hay `lan*` | El switch/PHY no probeó; mira `dmesg` y el diagnóstico del init |
| `Demo license expired` | Esperado en esta NAND; no es un fallo del arranque |

Más detalle en **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**. La NAND y UBI se
explican en **[NAND-UBI.md](NAND-UBI.md)**.
