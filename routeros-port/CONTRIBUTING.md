# Contribuir

Gracias por querer ayudar. Este es un proyecto de investigación de hardware:
la prioridad es **no romper el router de nadie** y que los resultados sean
reproducibles.

## Alcance

Se aceptan:

- correcciones de documentación y comandos;
- mejoras de reproducibilidad (rutas, dependencias, scripts portables);
- diagnóstico de NAND/UBI, switch, PHY, consola o arranque;
- drivers propios y parches GPL compatibles;
- pruebas en hardware con logs redactados.

**No se aceptan:**

- `.npk`, rootfs, volcados de NAND, firmware propietario o cualquier software de
  MikroTik/Genexis;
- *keygens*, parches de licencia, bypass del *software ID* o instrucciones para
  evitar el chequeo de licencia;
- credenciales, IPs públicas, MACs, números de serie o backups personales.

## Antes de tocar hardware

- El método por defecto es **TFTP a RAM**; no escribas NAND.
- Si propones un cambio de NAND/UBI, incluye backup, geometría y plan de
  recuperación. Sin eso no se revisa.
- Prueba primero en tu unidad y documenta la revisión de la placa, el U-Boot y
  el log.
- No publiques un `.y3` ni un `uImage` que contenga rootfs de RouterOS.

## Flujo de trabajo

1. Abre un issue con el template de bug/hardware antes de un cambio grande.
2. Crea una rama descriptiva: `docs/...`, `fix/...`, `feat/...`.
3. Haz cambios pequeños y explicables. No reformatees archivos enteros sin
   necesidad.
4. Si tocas el kernel o el init, ejecuta el build y adjunta el resultado:
   ```bash
   sudo bash build-563.sh
   md5sum out/uImage-563
   ```
5. Si tocas la documentación, revisa los enlaces relativos y actualiza
   `progress.json` si cambia un hito. Regenera el SVG:
   ```bash
   python3 tools/progress.py
   ```
6. Abre el PR con la plantilla y marca lo que **no** has podido probar.

## Estilo

- Los documentos y comentarios pueden estar en español; los identificadores y
  comandos, en el idioma que ya use el archivo.
- En shell, usa `set -u`/`set -e` cuando tenga sentido y cita variables.
- En Python, sigue el estilo de los scripts existentes; no añadas dependencias
  si la biblioteca estándar basta.
- No dejes rutas absolutas de tu máquina en scripts nuevos. Usa
  `$(cd "$(dirname "$0")" && pwd)` o una variable de entorno.
- No añadas logs, `out/`, `ros/` ni `__pycache__/` al commit.

## Checklist del PR

- [ ] El cambio está descrito y limitado a un objetivo.
- [ ] No incluye software propietario, rootfs, `.npk` ni volcados.
- [ ] No incluye credenciales, IPs/MACs ni datos personales.
- [ ] `build-563.sh` sigue funcionando (si aplica).
- [ ] La documentación afectada está actualizada.
- [ ] `progress.json` y `progress.svg` están sincronizados (si aplica).
- [ ] Sé qué parte no he podido probar y lo digo en el PR.
