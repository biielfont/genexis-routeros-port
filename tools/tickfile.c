/*
 * tickfile - reloj de jiffies para RouterOS en el ED500.
 *
 * libumsg abre /dev/jiffies, hace mmap de 8 KiB y lee un uint32 en el
 * offset 0 para calcular todos sus timeouts.  El modulo jiffies.ko del
 * rootfs mapea la pagina con un PFN incorrecto y provoca Bus error.
 *
 * Este helper mantiene /dev/jiffies como un fichero regular de 8 KiB en
 * tmpfs y escribe el contador a 100 Hz, que es lo que espera libumsg,
 * independientemente de que el kernel vaya a CONFIG_HZ=250.  Al ser
 * MAP_SHARED, las escrituras con pwrite se ven en el mmap de libumsg.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>

/* RouterOS (libumsg::getJiffies) suma 30000 = 300*100 al valor del
 * fichero y espera un reloj de 100 Hz. El kernel de este port va a
 * CONFIG_HZ=250, pero /dev/jiffies lo consume el userland: este helper
 * emula el reloj de 100 Hz de MikroTik, no el del kernel. */
#define ROS_HZ 100
#define NS_PER_TICK (1000000000ULL / ROS_HZ)
/* Jiffies crudos de 100 Hz: Linux arranca en INITIAL_JIFFIES=-300*HZ.
 * getJiffies() suma 30000, asi que el valor visible empieza en 0. */
#define INITIAL_JIFFIES ((uint32_t)(-300 * ROS_HZ))

int main(void)
{
    int fd = open("/dev/jiffies", O_RDWR);
    if (fd < 0)
        return 1;

    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        return 2;

    uint64_t base_ns = (uint64_t)ts.tv_sec * 1000000000ULL +
                       (uint64_t)ts.tv_nsec;

    for (;;) {
        if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
            return 3;
        uint64_t now_ns = (uint64_t)ts.tv_sec * 1000000000ULL +
                          (uint64_t)ts.tv_nsec;
        uint32_t elapsed = (uint32_t)((now_ns - base_ns) / NS_PER_TICK);
        uint32_t j = (uint32_t)(INITIAL_JIFFIES + elapsed);
        unsigned char b[4] = {
            (unsigned char)(j >> 24),
            (unsigned char)(j >> 16),
            (unsigned char)(j >> 8),
            (unsigned char)j,
        };
        (void)pwrite(fd, b, sizeof(b), 0);
        usleep(4000);
    }
}
