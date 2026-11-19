/*
 * phyreg - lee registros MII de un PHY a traves del netdev.
 *
 *   phyreg lan1 0 1 9 10
 *
 * Sirve para ver desde el initramfs lo que el PHY ve de verdad: BMCR (0),
 * BMSR (1, el bit 2 es el link), el anuncio de 1000BASE-T (9) y su estado
 * (10). Sin ethtool ni mii-tool en el initramfs, es la unica forma de
 * distinguir "el PHY no ve cable" de "el driver no se entera del link".
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/mii.h>
#include <linux/sockios.h>

int main(int argc, char **argv)
{
	struct mii_ioctl_data *mii;
	struct ifreq ifr;
	int fd, i;

	if (argc < 3) {
		fprintf(stderr, "uso: phyreg <iface> <reg> [reg...]\n");
		return 1;
	}

	fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("socket");
		return 1;
	}

	memset(&ifr, 0, sizeof(ifr));
	strncpy(ifr.ifr_name, argv[1], IFNAMSIZ - 1);
	ifr.ifr_name[IFNAMSIZ - 1] = '\0';
	mii = (struct mii_ioctl_data *)&ifr.ifr_data;

	if (ioctl(fd, SIOCGMIIPHY, &ifr) < 0) {
		perror("SIOCGMIIPHY");
		close(fd);
		return 2;
	}
	printf("%s: phy addr %u\n", argv[1], mii->phy_id);

	for (i = 2; i < argc; i++) {
		char *end = NULL;
		long reg = strtol(argv[i], &end, 0);

		if (!end || *end || reg < 0 || reg > 31) {
			fprintf(stderr, "registro invalido: %s\n", argv[i]);
			continue;
		}
		mii->reg_num = (unsigned short)reg;
		if (ioctl(fd, SIOCGMIIREG, &ifr) < 0) {
			perror("SIOCGMIIREG");
			continue;
		}
		printf("  reg %2ld = 0x%04x\n", reg, mii->val_out);
	}

	close(fd);
	return 0;
}
