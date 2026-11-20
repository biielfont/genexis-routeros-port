/*
 * swstats - vuelca los contadores del driver de un netdev (ETHTOOL_GSTATS).
 *
 *   swstats lan1
 *
 * El driver gswip publica ahi los contadores RMON de cada puerto del switch,
 * asi que sirve para separar "el cable no entrega" de "el switch no reenvia"
 * sin necesidad de ethtool.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/ethtool.h>
#include <linux/sockios.h>

int main(int argc, char **argv)
{
	struct ethtool_sset_info *sset;
	struct ethtool_gstrings *strings;
	struct ethtool_stats *stats;
	struct ifreq ifr;
	char buf[8192];
	int fd, i, n;
	unsigned int len;

	if (argc < 2) {
		fprintf(stderr, "uso: swstats <iface>\n");
		return 1;
	}

	fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("socket");
		return 1;
	}

	memset(buf, 0, sizeof(buf));
	sset = (struct ethtool_sset_info *)buf;
	sset->cmd = ETHTOOL_GSSET_INFO;
	sset->sset_mask = 1ULL << ETH_SS_STATS;
	memset(&ifr, 0, sizeof(ifr));
	strncpy(ifr.ifr_name, argv[1], IFNAMSIZ - 1);
	ifr.ifr_data = (void *)sset;
	if (ioctl(fd, SIOCETHTOOL, &ifr) < 0 || !sset->data[0]) {
		perror("ETHTOOL_GSSET_INFO");
		close(fd);
		return 2;
	}
	n = (int)sset->data[0];

	len = sizeof(*strings) + n * ETH_GSTRING_LEN;
	strings = calloc(1, len);
	stats = calloc(1, sizeof(*stats) + n * sizeof(uint64_t));
	if (!strings || !stats) {
		fprintf(stderr, "sin memoria\n");
		close(fd);
		return 1;
	}
	strings->cmd = ETHTOOL_GSTRINGS;
	strings->string_set = ETH_SS_STATS;
	strings->len = n;
	memset(&ifr, 0, sizeof(ifr));
	strncpy(ifr.ifr_name, argv[1], IFNAMSIZ - 1);
	ifr.ifr_data = (void *)strings;
	if (ioctl(fd, SIOCETHTOOL, &ifr) < 0) {
		perror("ETHTOOL_GSTRINGS");
		close(fd);
		return 2;
	}

	stats->cmd = ETHTOOL_GSTATS;
	stats->n_stats = n;
	memset(&ifr, 0, sizeof(ifr));
	strncpy(ifr.ifr_name, argv[1], IFNAMSIZ - 1);
	ifr.ifr_data = (void *)stats;
	if (ioctl(fd, SIOCETHTOOL, &ifr) < 0) {
		perror("ETHTOOL_GSTATS");
		close(fd);
		return 2;
	}

	for (i = 0; i < n; i++) {
		const char *name = (const char *)strings->data + i * ETH_GSTRING_LEN;
		printf("%-28s %llu\n", name, (unsigned long long)stats->data[i]);
	}

	close(fd);
	return 0;
}
