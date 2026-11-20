## Qué cambia

<!-- Una o dos frases. Enlaza el issue si existe. -->

## Por qué

<!-- El problema que resuelve y cómo lo has comprobado. -->

## Pruebas

- [ ] `sudo bash build-563.sh` (si toca kernel/init)
- [ ] Arranque por TFTP en hardware (si toca kernel/init)
- [ ] `python3 tools/progress.py` (si toca `progress.json`; regenera `progress.svg`)
- [ ] Enlaces/documentación revisados

## Checklist legal y de seguridad

- [ ] No incluyo `.npk`, rootfs, volcados de NAND ni software propietario.
- [ ] No incluyo credenciales, IPs, MACs ni números de serie.
- [ ] No incluyo un bypass de licencia ni instrucciones para evitarla.
- [ ] Si toca NAND, explico backup, geometría y plan de recuperación.

## Lo que no he podido probar

<!-- Sé explícito; es mejor que dar por hecho una prueba que no existe. -->
