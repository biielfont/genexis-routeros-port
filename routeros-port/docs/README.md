# Documentación

El punto de entrada del proyecto es el [README](../README.md). Esta carpeta
separa lo que está vigente de lo que es historia de la investigación.

## Guías actuales

| Documento | Para qué |
|---|---|
| [BUILD.md](BUILD.md) | Preparar toolchain/fuentes, compilar y verificar `out/uImage-563` |
| [BOOT-TFTP.md](BOOT-TFTP.md) | Arrancar por TFTP a RAM, cazar U-Boot y resetear en remoto |
| [NAND-UBI.md](NAND-UBI.md) | Geometría NAND, BCH-4/BBT, attach UBI y montaje en lectura |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Fallos típicos, logs y qué comprobar |
| [PROGRESS.md](PROGRESS.md) | Cómo se calcula y se actualiza el mapa de progreso |
| [FLASH-Y3.md](FLASH-Y3.md) | Investigación del contenedor `.y3` (experimental, no método actual) |

## Mapa de progreso

El gráfico es **[../progress.svg](../progress.svg)** y se embebe en el
[README](../README.md) y en [PROGRESS.md](PROGRESS.md). Se genera desde
`progress.json` con `tools/progress.py`; no hay página HTML ni tabla visual
mantenida a mano.

## Histórico

Estos documentos se conservan para que se vea **cómo** se llegó hasta aquí. No
describen el estado actual y pueden contener rutas o conclusiones antiguas:

- [history/CHECKLIST-2026-11.md](history/CHECKLIST-2026-11.md) — primera puesta
  en marcha y auditoría previa.
- [history/NOTES-5.6.3-port.md](history/NOTES-5.6.3-port.md) — notas del port
  del driver GSWIP y errores de compilación.

## Reglas de documentación

- Los comandos deben poder copiarse y ejecutarse desde la raíz del repo.
- Las rutas absolutas de una máquina concreta no deben ser necesarias para
  entender el procedimiento; si un script las usa, se documenta como histórico.
- Los logs, el rootfs, el `.npk` y los artefactos de `out/` no se commitean.
- Si cambia un hito, actualiza `progress.json` y regenera `progress.svg` con
  `python3 tools/progress.py`.
