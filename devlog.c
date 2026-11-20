/* devlog: crea el socket /dev/log y vuelca los mensajes a
 * /flash/rw/logs/messages. Es el reemplazo del syslogd de BusyBox, que en
 * este devtmpfs deja el nodo sin visible. No toca NAND ni licencia. */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	const char *path = (argc > 1) ? argv[1] : "/dev/log";
	int fd;
	struct sockaddr_un sa;
	char buf[8192];

	fd = socket(AF_UNIX, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("devlog: socket");
		return 1;
	}

	memset(&sa, 0, sizeof(sa));
	sa.sun_family = AF_UNIX;
	strncpy(sa.sun_path, path, sizeof(sa.sun_path) - 1);

	unlink(path);
	if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
		perror("devlog: bind");
		return 1;
	}
	chmod(path, 0666);
	fprintf(stderr, "devlog: %s listo\n", path);

	for (;;) {
		ssize_t n = recv(fd, buf, sizeof(buf), 0);
		int out;

		if (n <= 0)
			continue;
		out = open("/flash/rw/logs/messages",
			   O_WRONLY | O_CREAT | O_APPEND, 0644);
		if (out >= 0) {
			write(out, buf, n);
			close(out);
		}
	}
	return 0;
}
