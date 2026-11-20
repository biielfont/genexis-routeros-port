/* Mini-strace para MIPS o32: ejecuta un programa y registra open/openat/
 * execve con su resultado. Sirve para localizar el "broken path" de
 * sysinit sin LD_PRELOAD ni modificar el rootfs.
 *
 * Uso: sysopen /sbin/sysinit start
 * Log: /flash/rw/trace.log
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/types.h>

struct mips_regs {
	unsigned long regs[32];
};

#define NR_open   4005
#define NR_openat 4288
#define NR_execve 4022

#define MAXT 64

struct task {
	pid_t pid;
	int in_syscall;
};

static struct task tasks[MAXT];
static int ntasks;
static FILE *logf;

static struct task *get_task(pid_t pid)
{
	int i;
	for (i = 0; i < ntasks; i++)
		if (tasks[i].pid == pid)
			return &tasks[i];
	if (ntasks >= MAXT)
		return NULL;
	tasks[ntasks].pid = pid;
	tasks[ntasks].in_syscall = 0;
	return &tasks[ntasks++];
}

static int read_path(pid_t pid, unsigned long addr, char *buf, int max)
{
	char p[40];
	int fd, n;

	if (!addr)
		return -1;
	snprintf(p, sizeof(p), "/proc/%d/mem", (int)pid);
	fd = open(p, O_RDONLY);
	if (fd < 0)
		return -1;
	n = (int)pread(fd, buf, max - 1, (off_t)addr);
	close(fd);
	if (n <= 0)
		return -1;
	buf[n] = 0;
	return n;
}

static void log_syscall(pid_t pid, const char *name, const char *path,
			long ret, int entry)
{
	if (!logf)
		return;
	if (entry) {
		fprintf(logf, "[%d] %s(\"%s\") ...\n", (int)pid, name,
			path ? path : "(null)");
	} else {
		fprintf(logf, "[%d] %s -> %ld", (int)pid, name, ret);
		if (ret < 0)
			fprintf(logf, " errno=%ld", -ret);
		fprintf(logf, "\n");
	}
	fflush(logf);
}

int main(int argc, char **argv)
{
	pid_t pid;
	int st, status;
	struct mips_regs r;
	struct task *t;
	char path[512];

	if (argc < 2) {
		fprintf(stderr, "uso: sysopen PROG [args...]\n");
		return 2;
	}

	logf = fopen("/flash/rw/trace.log", "w");
	if (!logf)
		logf = stderr;
	else
		setvbuf(logf, NULL, _IONBF, 0);

	pid = fork();
	if (pid == 0) {
		ptrace(PTRACE_TRACEME, 0, 0, 0);
		execvp(argv[1], &argv[1]);
		_exit(127);
	}
	if (pid < 0) {
		perror("fork");
		return 1;
	}

	if (waitpid(pid, &st, 0) < 0) {
		perror("waitpid");
		return 1;
	}
	if (ptrace(PTRACE_SETOPTIONS, pid, 0,
		   PTRACE_O_TRACESYSGOOD | PTRACE_O_TRACEFORK |
		   PTRACE_O_TRACEVFORK | PTRACE_O_TRACECLONE |
		   PTRACE_O_TRACEEXEC) < 0) {
		perror("PTRACE_SETOPTIONS");
	}
	get_task(pid);

	for (;;) {
		int i, alive = 0;

		for (i = 0; i < ntasks; i++) {
			if (ptrace(PTRACE_SYSCALL, tasks[i].pid, 0, 0) == 0)
				alive = 1;
		}
		if (!alive)
			break;

		status = waitpid(-1, &st, __WALL);
		if (status < 0) {
			if (errno == ECHILD)
				break;
			continue;
		}

		if (WIFEXITED(st) || WIFSIGNALED(st))
			continue;

		if (!WIFSTOPPED(st))
			continue;

		if (WSTOPSIG(st) == SIGTRAP) {
			int event = (st >> 16) & 0xff;
			if (event == PTRACE_EVENT_FORK ||
			    event == PTRACE_EVENT_VFORK ||
			    event == PTRACE_EVENT_CLONE) {
				unsigned long newpid = 0;
				if (ptrace(PTRACE_GETEVENTMSG, status, 0,
					   &newpid) == 0 && newpid)
					get_task((pid_t)newpid);
			}
		}

		if (WSTOPSIG(st) == (SIGTRAP | 0x80)) {
			t = get_task(status);
			if (!t)
				continue;
			if (ptrace(PTRACE_GETREGS, status, 0, &r) < 0)
				continue;
			{
				long nr = (long)r.regs[2];
				const char *name = NULL;

				if (nr == NR_open) {
					name = "open";
					read_path(status, r.regs[4], path, sizeof(path));
				} else if (nr == NR_openat) {
					name = "openat";
					read_path(status, r.regs[5], path, sizeof(path));
				} else if (nr == NR_execve) {
					name = "execve";
					read_path(status, r.regs[4], path, sizeof(path));
				}
				if (name) {
					log_syscall(status, name, path,
						    t->in_syscall ? 0 : (long)r.regs[2],
						    !t->in_syscall);
					t->in_syscall = !t->in_syscall;
				}
			}
		}
	}

	if (logf != stderr)
		fclose(logf);
	return 0;
}
