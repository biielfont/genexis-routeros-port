/*
 * timediag - comprueba si el kernel de este port duerme de verdad.
 *
 * En el ED500 se observo que /bin/busybox sleep 30 volvia en ~0,15 s
 * mientras date avanzaba en tiempo real.  La primera version devolvia -1
 * cuando clock_gettime fallaba, y eso se confundia con "no pasa el tiempo",
 * asi que esta imprime los valores crudos y los codigos de error de cada
 * llamada: no oculta nada.
 *
 * Mide las tres formas de dormir que usa el userland (sleep, usleep,
 * nanosleep) y las dos que usa RouterOS en sus bucles de eventos (poll y
 * select con timeout).  Si esas dos vuelven al instante, todos los
 * timeouts de RouterOS (login, www, parser, user) caducan solos.
 *
 * La espera activa final es la referencia: cuantas vueltas de
 * clock_gettime hacen falta para que CLOCK_MONOTONIC avance un segundo.
 */
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/select.h>
#include <sys/time.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t alarma;
static void golpe(int s) { (void)s; alarma++; }

static double reloj(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0)
        return -1.0;
    return (double)t.tv_sec + (double)t.tv_nsec / 1e9;
}

static void crudo(const char *et)
{
    struct timespec m, r;
    char up[64] = "?";
    FILE *f;
    int rm, rr;

    if (clock_gettime(CLOCK_MONOTONIC, &m) != 0)
        m.tv_sec = -1, m.tv_nsec = 0;
    if (clock_gettime(CLOCK_REALTIME, &r) != 0)
        r.tv_sec = -1, r.tv_nsec = 0;
    rm = (int)m.tv_sec;
    rr = (int)r.tv_sec;

    f = fopen("/proc/uptime", "r");
    if (f) {
        if (!fgets(up, sizeof up, f))
            strcpy(up, "read-fail");
        fclose(f);
        up[strcspn(up, "\r\n")] = 0;
    }

    printf("timediag %-14s mono=%ld.%09ld real=%ld.%09ld uptime=%s\n",
           et, (long)m.tv_sec, m.tv_nsec, (long)r.tv_sec, r.tv_nsec, up);
    (void)rm;
    (void)rr;
}

static void prueba(const char *et, int rc)
{
    printf("timediag %-14s rc=%d%s%s\n", et, rc,
           rc ? " errno=" : "", rc ? strerror(errno) : "");
    crudo(et);
}

int main(void)
{
    struct timespec ts = { 1, 0 };
    struct timeval tv = { 1, 0 };
    struct timespec a, b;
    struct itimerval it;
    struct itimerspec its;
    long vueltas = 0;
    int rc, tfd;
    double tr;

    /* H44: el init lanza timediag por una tuberia, asi que stdout va con
     * buffer completo y un panic se lleva las lineas sin imprimir (paso en
     * H43: el reinicio a up=16 no dejo ni una linea).  Se escribe directo
     * en /dev/ttyS0 y sin buffer: cada marca sale antes de la llamada que
     * pueda matar la placa. */
    {
        FILE *t = fopen("/dev/ttyS0", "w");
        if (t) {
            dup2(fileno(t), 1);
            fclose(t);
        }
    }
    setvbuf(stdout, NULL, _IONBF, 0);

    printf("timediag: inicio\n");
    printf("timediag clk_tck=%ld\n", (long)sysconf(_SC_CLK_TCK));
    crudo("inicio");

    errno = 0;
    rc = (int)sleep(2);
    prueba("sleep(2)", rc);

    errno = 0;
    rc = nanosleep(&ts, NULL);
    prueba("nanosleep(1s)", rc);

    errno = 0;
    rc = usleep(1000000);
    prueba("usleep(1s)", rc);

    errno = 0;
    rc = poll(NULL, 0, 1000);
    prueba("poll(1s)", rc);

    errno = 0;
    rc = select(0, NULL, NULL, NULL, &tv);
    prueba("select(1s)", rc);

    /* H42: el motor de scripts de sysinit aborta con "interrupted", que es
     * el error de un syscall que devuelve EINTR.  Se prueban los cuatro
     * mecanismos con los que un motor asi puede cortar un script. */
    printf("timediag MARCA: signal()+alarm(1)\n");
    alarma = 0;
    signal(SIGALRM, golpe);
    errno = 0;
    rc = alarm(1);
    printf("timediag alarm(1)     rc=%d\n", rc);
    tr = reloj();
    rc = poll(NULL, 0, 2500);
    printf("timediag alarm+poll  rc=%d errno=%s alarma=%d dt=%.3f\n",
           rc, rc < 0 ? strerror(errno) : "-", (int)alarma, reloj() - tr);

    printf("timediag MARCA: setitimer\n");
    alarma = 0;
    memset(&it, 0, sizeof(it));
    it.it_value.tv_sec = 1;
    errno = 0;
    rc = setitimer(ITIMER_REAL, &it, NULL);
    printf("timediag setitimer    rc=%d%s%s\n", rc,
           rc ? " errno=" : "", rc ? strerror(errno) : "");
    tr = reloj();
    rc = poll(NULL, 0, 2500);
    printf("timediag itimer+poll rc=%d errno=%s alarma=%d dt=%.3f\n",
           rc, rc < 0 ? strerror(errno) : "-", (int)alarma, reloj() - tr);

    printf("timediag MARCA: timerfd_create\n");
    tfd = timerfd_create(CLOCK_MONOTONIC, 0);
    if (tfd >= 0) {
        memset(&its, 0, sizeof(its));
        its.it_value.tv_sec = 1;
        rc = timerfd_settime(tfd, 0, &its, NULL);
        tr = reloj();
        {
            struct pollfd pf = { tfd, POLLIN, 0 };
            int r2 = poll(&pf, 1, 2500);
            printf("timediag timerfd     set=%d poll=%d rev=%#x dt=%.3f\n",
                   rc, r2, (unsigned)pf.revents, reloj() - tr);
        }
        close(tfd);
    } else {
        printf("timediag timerfd     create FALLO errno=%s\n",
               strerror(errno));
    }

    printf("timediag MARCA: clock_nanosleep\n");
    errno = 0;
    rc = clock_nanosleep(CLOCK_MONOTONIC, 0, &ts, NULL);
    prueba("clock_nanosleep", rc);

    /* referencia: no usa el temporizador, solo el reloj */
    clock_gettime(CLOCK_MONOTONIC, &a);
    do {
        clock_gettime(CLOCK_MONOTONIC, &b);
        vueltas++;
        if (vueltas > 500000000L)
            break;
    } while ((b.tv_sec - a.tv_sec) < 1);
    printf("timediag giro           vueltas=%ld mono=%ld.%09ld->%ld.%09ld\n",
           vueltas, (long)a.tv_sec, a.tv_nsec, (long)b.tv_sec, b.tv_nsec);

    printf("timediag: fin\n");
    return 0;
}
