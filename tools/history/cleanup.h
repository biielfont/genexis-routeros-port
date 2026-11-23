/* SPDX-License-Identifier: GPL-2.0 */
/* cleanup.h minimo para el 5.6.3 del port: solo lo que usa el conduit CBM.
 * Implementa guard() y scoped_guard() para mutex, con la misma forma que el
 * cleanup.h del kernel 6.5+, para no tocar el codigo del driver.
 */
#ifndef _LINUX_CLEANUP_H
#define _LINUX_CLEANUP_H

#include <linux/compiler.h>
#include <linux/mutex.h>

#define __cleanup(fn)	__attribute__((cleanup(fn)))

/* CLASS(nombre, var)(args) declara var con liberacion automatica al salir
 * del ambito, llamando al constructor con args.
 */
#define CLASS(_name, var)						\
	__class_##_name##_t var __cleanup(__class_##_name##_destructor) = \
		__class_##_name##_constructor

#define guard(_name)	CLASS(_name, __UNIQUE_ID(guard))

/* Ejecuta el cuerpo una sola vez, con el recurso tomado, y lo suelta al salir:
 * el incremento marca done y la condicion termina el bucle.
 */
#define scoped_guard(_name, args...)					\
	for (CLASS(_name, scope)(args), *done = NULL; !done; done = (void *)1)

/* --- mutex --- */
typedef struct mutex *__class_mutex_t;

static inline void __class_mutex_destructor(__class_mutex_t *p)
{
	mutex_unlock(*p);
}

static inline __class_mutex_t __class_mutex_constructor(struct mutex *m)
{
	mutex_lock(m);
	return m;
}

#endif /* _LINUX_CLEANUP_H */
