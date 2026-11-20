# Seguridad

## Qué reportar

- Un fallo que pueda dejar la placa sin arranque (por ejemplo, un cambio que
  escriba NAND o un reset que no funcione).
- Exposición de credenciales, claves, logs con datos personales o backups.
- Un bypass de licencia o una instrucción que lo permita.

## Cómo reportarlo

No abras un issue público con datos sensibles. Usa el canal privado del
mantenedor del repositorio o un *security advisory* de GitHub si está
disponible. Incluye:

- versión del repo/commit;
- modelo y revisión de la placa;
- pasos mínimos para reproducir;
- log redactado;
- impacto y si has probado una recuperación.

## Datos que no deben publicarse

- IPs públicas, MACs, números de serie y claves;
- volcados de NAND, `.npk`, rootfs o `.y3` con contenido propietario;
- credenciales de RouterOS, WiFi o del ISP;
- logs completos sin redactar.

## Alcance

Este proyecto arranca por TFTP a RAM y no escribe NAND por defecto. Cualquier
contribución que cambie eso debe explicar el riesgo, el backup y la recuperación
antes de mergearse.
