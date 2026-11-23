/* Interceptor minimo de open/openat para localizar el "broken path" de
 * sysinit en RouterOS MIPS o32. Se carga con LD_PRELOAD=/flash/openlog.so.
 * No usa libc: solo syscalls crudas, para no depender de la uClibc del
 * rootfs. Escribe cada open en /flash/rw/open.log.
 *
 * No toca la licencia ni la identidad: solo observa rutas. */
typedef unsigned int mode_t;

#define O_WRONLY  0x0001
#define O_CREAT   0x0100
#define O_APPEND  0x0008

#define AT_FDCWD  (-100)
#define NR_open   4005
#define NR_openat 4288
#define NR_write  4004
#define NR_close  4006

extern int *__errno_location(void);

static long sys1(long n, long a)
{
	register long v0 asm("$2") = n;
	register long a0 asm("$4") = a;
	register long a3 asm("$7");
	asm volatile("syscall" : "+r"(v0), "=r"(a3) : "r"(a0) : "$3", "memory");
	return v0;
}

static long sys3(long n, long a, long b, long c)
{
	register long v0 asm("$2") = n;
	register long a0 asm("$4") = a;
	register long a1 asm("$5") = b;
	register long a2 asm("$6") = c;
	register long a3 asm("$7");
	asm volatile("syscall" : "+r"(v0), "=r"(a3)
		     : "r"(a0), "r"(a1), "r"(a2) : "$3", "memory");
	return v0;
}

static long sys4(long n, long a, long b, long c, long d)
{
	register long v0 asm("$2") = n;
	register long a0 asm("$4") = a;
	register long a1 asm("$5") = b;
	register long a2 asm("$6") = c;
	register long a3 asm("$7") = d;
	asm volatile("syscall" : "+r"(v0), "+r"(a3)
		     : "r"(a0), "r"(a1), "r"(a2) : "$3", "memory");
	return v0;
}

static int app(char *b, int p, const char *s)
{
	while (s && *s && p < 500)
		b[p++] = *s++;
	return p;
}

static int appnum(char *b, int p, long v)
{
	char t[24];
	int n = 0;
	unsigned long u;

	if (v < 0) {
		if (p < 500)
			b[p++] = '-';
		u = (unsigned long)(-v);
	} else {
		u = (unsigned long)v;
	}
	do {
		t[n++] = '0' + (u % 10);
		u /= 10;
	} while (u && n < 20);
	while (n > 0 && p < 500)
		b[p++] = t[--n];
	return p;
}

static void logit(const char *tag, const char *path, long r)
{
	char b[512];
	int p = 0;
	long fd;

	p = app(b, p, tag);
	p = app(b, p, " ");
	p = app(b, p, path ? path : "(null)");
	p = app(b, p, " ret=");
	p = appnum(b, p, r);
	if (r < 0) {
		p = app(b, p, " errno=");
		p = appnum(b, p, -r);
	}
	p = app(b, p, "\n");

	fd = sys4(NR_openat, AT_FDCWD, (long)"/flash/rw/open.log",
		  O_WRONLY | O_APPEND | O_CREAT, 0644);
	if (fd >= 0) {
		sys3(NR_write, fd, (long)b, p);
		sys1(NR_close, fd);
	}
}

static int ret(long r)
{
	if (r < 0) {
		*__errno_location() = (int)(-r);
		return -1;
	}
	return (int)r;
}

int open(const char *path, int flags, ...)
{
	mode_t mode = 0;
	long r;

	if (flags & O_CREAT) {
		__builtin_va_list ap;
		__builtin_va_start(ap, flags);
		mode = __builtin_va_arg(ap, mode_t);
		__builtin_va_end(ap);
	}
	r = sys3(NR_open, (long)path, flags, mode);
	logit("open", path, r);
	return ret(r);
}

int open64(const char *path, int flags, ...)
	__attribute__((alias("open")));

int openat(int dirfd, const char *path, int flags, ...)
{
	mode_t mode = 0;
	long r;

	if (flags & O_CREAT) {
		__builtin_va_list ap;
		__builtin_va_start(ap, flags);
		mode = __builtin_va_arg(ap, mode_t);
		__builtin_va_end(ap);
	}
	r = sys4(NR_openat, dirfd, (long)path, flags, mode);
	logit("openat", path, r);
	return ret(r);
}

int openat64(int dirfd, const char *path, int flags, ...)
	__attribute__((alias("openat")));
