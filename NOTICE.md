# Notice / Aviso legal

Este es un proyecto de investigación independiente. **No está afiliado,
patrocinado ni respaldado por MikroTik, Genexis o Intel/Lantiq.** Los nombres y
marcas pertenecen a sus titulares.

## Software de terceros

- **RouterOS y el `.npk`** son software propietario de MikroTik. No se incluyen
  en este repositorio y no se redistribuyen. Se obtienen de MikroTik bajo sus
  propios términos y licencia.
- **El rootfs de RouterOS** tampoco se incluye. `ros/` está ignorado por git.
- **El kernel 5.6.3 y el parche GPL de MikroTik** se descargan de las fuentes
  publicadas por MikroTik. Tienen su propia licencia (GPL-2.0 para el kernel;
  consulta los archivos `COPYING` del árbol). Los parches de este repo se
  aplican sobre ese árbol y no cambian esa licencia.
- **U-Boot, BusyBox, Dropbear y las herramientas del sistema** conservan sus
  licencias originales.

## Licencia de este repositorio

Este repositorio no incluye un archivo `LICENSE` porque la mezcla de scripts
propios, parches derivados del kernel GPL y documentación debe decidirse con
cuidado antes de publicar. **No se concede ninguna licencia implícita sobre el
código propio más allá de lo que permita la ley aplicable.** Antes de
redistribuir el proyecto, el mantenedor debe añadir la licencia elegida y
revisar la compatibilidad con GPL-2.0.

## Licencia de RouterOS

Este repositorio **no contiene ni pretende contener** un método para saltarse la
licencia de RouterOS. El fallo `Demo license expired!` es el comportamiento
esperado cuando no hay una licencia válida para el hardware. Si quieres usar
RouterOS, necesitas una licencia de MikroTik.

## Seguridad

No publiques logs con IPs, MACs, números de serie, claves, backups de NAND o
cualquier dato de tu red. No ejecutes comandos de escritura de NAND sin backup
y plan de recuperación.
