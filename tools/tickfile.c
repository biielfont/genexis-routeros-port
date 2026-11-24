/*
 * tickfile - reloj de jiffies para RouterOS en el ED500.
 *
 * libumsg abre /dev/jiffies, hace mmap de 8 KiB y lee un uint32 en el
 * offset 0 para calcular todos sus timeouts.  El modulo jiffies.ko del
 * rootfs mapea la pagina con un PFN incorrecto y provoca Bus error.
 *
 * Este helper mantiene /dev/jiffies como un fichero regular de 8 KiB en
 * tmpfs y escribe el contador a 250 Hz (CONFIG_HZ=250).  Al ser MAP_SHARED,
 * las escrituras con pwrite se ven en el mmap de libumsg.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>

#define HZ 250
#define NS_PER_TICK (1000000000ULL / HZ)

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
        uint32_t j = (uint32_t)((now_ns - base_ns) / NS_PER_TICK);
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
