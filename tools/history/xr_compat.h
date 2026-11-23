/* xr_compat.h - capa de compatibilidad para portar el driver GSWIP del XRX500
 * del arbol 6.18 al kernel 5.6.3 de MikroTik.
 *
 * Comprobado en este arbol (no supuesto):
 *   - no existen dsa_user_to_port() ni dsa_slave_to_port() publicas: el mapeo
 *     netdev -> puerto solo esta dentro de net/dsa (dsa_priv.h). Por eso
 *     tag_gswip3.c vive en net/dsa/ y no aqui.
 *   - dev->dsa_ptr es struct dsa_port *.
 *   - no hay iteradores dsa_switch_for_each_* ni dsa_cpu_ports().
 *
 * Los iteradores de abajo conservan la forma del 6.18:
 *     dsa_switch_for_each_user_port(dp, ds) { ... }
 * que se expande a un for + if y por tanto admite un bloque detras.
 */
#ifndef _XR_COMPAT_H
#define _XR_COMPAT_H

#include <linux/version.h>
#include <linux/device.h>
#include <linux/regmap.h>
#include <net/dsa.h>

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 0, 0)

/* dev_err_probe(): llego en 5.9. */
#ifndef dev_err_probe
#define dev_err_probe(dev, err, fmt, ...)				\
	({								\
		int __xr_e = (err);					\
		if (__xr_e != -EPROBE_DEFER)				\
			dev_err(dev, fmt, ##__VA_ARGS__);		\
		__xr_e;							\
	})
#endif

/* regmap_set_bits()/regmap_clear_bits(): llegaron en 5.16. */
#ifndef regmap_set_bits
#define regmap_set_bits(map, reg, bits)					\
	regmap_update_bits((map), (reg), (bits), (bits))
#endif
#ifndef regmap_clear_bits
#define regmap_clear_bits(map, reg, bits)				\
	regmap_update_bits((map), (reg), (bits), 0)
#endif

/* devm_of_mdiobus_register(): llego en 5.10. Sin devm: se libera en remove(). */
#ifndef devm_of_mdiobus_register
#define devm_of_mdiobus_register(dev, mdio, np)				\
	of_mdiobus_register((mdio), (np))
#endif

/* Helpers de puerto con nombre nuevo. */
#ifndef dsa_port_is_user
#define dsa_port_is_user(dp)		dsa_is_user_port((dp)->ds, (dp)->index)
#endif
#ifndef dsa_port_is_cpu
#define dsa_port_is_cpu(dp)		dsa_is_cpu_port((dp)->ds, (dp)->index)
#endif
#ifndef dsa_port_bridge_dev_get
#define dsa_port_bridge_dev_get(dp)	((dp)->bridge_dev)
#endif

/* dsa_phylink_to_port(): no existe en 5.6.3; el phylink_config va embebido
 * dentro del dsa_port.
 */
#ifndef dsa_phylink_to_port
static inline struct dsa_port *xr_phylink_to_port(struct phylink_config *pl)
{
	return container_of(pl, struct dsa_port, pl);
}
#define dsa_phylink_to_port(pl)	xr_phylink_to_port(pl)
#endif

/* Iteradores. */
#ifndef dsa_switch_for_each_port
#define dsa_switch_for_each_port(dp, ds)				\
	for (int __xr_i = 0; __xr_i < (ds)->num_ports; __xr_i++)		\
		if (((dp) = dsa_to_port((ds), __xr_i)))
#endif

#ifndef dsa_switch_for_each_user_port
#define dsa_switch_for_each_user_port(dp, ds)				\
	for (int __xr_i = 0; __xr_i < (ds)->num_ports; __xr_i++)		\
		if (((dp) = dsa_to_port((ds), __xr_i)) &&		\
		    dsa_is_user_port((ds), __xr_i))
#endif

#ifndef dsa_switch_for_each_cpu_port
#define dsa_switch_for_each_cpu_port(dp, ds)				\
	for (int __xr_i = 0; __xr_i < (ds)->num_ports; __xr_i++)		\
		if (((dp) = dsa_to_port((ds), __xr_i)) &&		\
		    dsa_is_cpu_port((ds), __xr_i))
#endif

/* En 6.18 dsa_cpu_ports(ds) se usa como EXPRESION que devuelve la mascara de
 * puertos CPU, no como iterador. Aqui se implementa igual.
 */
static inline unsigned long xr_cpu_port_mask(struct dsa_switch *ds)
{
	unsigned long mask = 0;

	for (int i = 0; i < ds->num_ports; i++)
		if (dsa_is_cpu_port(ds, i))
			mask |= BIT(i);

	return mask;
}
#define dsa_cpu_ports(ds)	xr_cpu_port_mask(ds)

#endif /* < 6.0 */

#endif /* _XR_COMPAT_H */
