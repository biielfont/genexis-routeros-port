#!/bin/bash
# Porta el tag DSA GSWIP3 (8 bytes) al 5.6.3. Sin el, el switch del XRX500 mete
# una cabecera de 8 bytes y DSA quita 4: la red no funciona.
set -e
K=/opt/ros-port/linux-5.6.3

# ---------- 1. enum ----------
python3 - <<'PY'
import re
p = "/opt/ros-port/linux-5.6.3/include/net/dsa.h"
s = open(p).read()
if "DSA_TAG_PROTO_GSWIP3_VALUE" in s:
    print("enum ya estaba")
else:
    s = s.replace("#define DSA_TAG_PROTO_AR9331_VALUE\t\t16\n",
                  "#define DSA_TAG_PROTO_AR9331_VALUE\t\t16\n#define DSA_TAG_PROTO_GSWIP3_VALUE\t\t17\n", 1)
    s = s.replace("\tDSA_TAG_PROTO_AR9331\t\t= DSA_TAG_PROTO_AR9331_VALUE,\n",
                  "\tDSA_TAG_PROTO_AR9331\t\t= DSA_TAG_PROTO_AR9331_VALUE,\n\tDSA_TAG_PROTO_GSWIP3\t\t= DSA_TAG_PROTO_GSWIP3_VALUE,\n", 1)
    open(p, "w").write(s)
    print("enum anadido")
PY

# ---------- 2. driver de tag ----------
cat > "$K/net/dsa/tag_gswip3.c" <<'EOF'
// SPDX-License-Identifier: GPL-2.0
/*
 * Intel / Lantiq GSWIP 3.0 (XRX500) PMAC tag support
 *
 * The switch prepends an eight byte header before the destination MAC
 * address, in both directions and with no EtherType marker to find it by.
 * Byte 2 carries the source port, byte 3 the transmit flags, and bytes 6/7
 * the destination port map.
 */

#include <linux/etherdevice.h>
#include <linux/skbuff.h>
#include <net/dsa.h>

#include "dsa_priv.h"

#define GSWIP3_NAME			"gswip3"
#define GSWIP3_HEADER_LEN		8

/* Byte 2 */
#define GSWIP3_SPPID_MASK		0xf0
#define GSWIP3_SPPID_SHIFT		4
#define  GSWIP3_SPPID_CPU		0

/* Byte 3, transmit only */
#define GSWIP3_TX_PORT_MAP_EN		0x80
#define GSWIP3_TX_TIME_DIS		0x20
#define GSWIP3_TX_CLASS_EN		0x10

static struct sk_buff *gswip3_tag_xmit(struct sk_buff *skb,
				       struct net_device *dev)
{
	struct dsa_port *dp = dsa_slave_to_port(dev);
	u8 *tag;
	int err;

	err = skb_cow_head(skb, GSWIP3_HEADER_LEN);
	if (err)
		return NULL;

	skb_push(skb, GSWIP3_HEADER_LEN);
	tag = skb->data;

	/* Bytes 0 and 1: checksum insertion offsets, all clear. */
	tag[0] = 0;
	tag[1] = 0;
	tag[2] = (GSWIP3_SPPID_CPU << GSWIP3_SPPID_SHIFT) & GSWIP3_SPPID_MASK;
	tag[3] = GSWIP3_TX_PORT_MAP_EN | GSWIP3_TX_CLASS_EN;
	tag[4] = 0;
	tag[5] = 0;

	/* Destination port map: ports 0-7 in byte 7, 8-15 in byte 6. */
	tag[6] = 0;
	tag[7] = 0;
	if (dp->index < 8)
		tag[7] = BIT(dp->index);
	else
		tag[6] = BIT(dp->index - 8);

	return skb;
}

static struct sk_buff *gswip3_tag_rcv(struct sk_buff *skb,
				      struct net_device *dev,
				      struct packet_type *pt)
{
	u8 *tag;
	int port;

	if (unlikely(!pskb_may_pull(skb, GSWIP3_HEADER_LEN)))
		return NULL;

	/* eth_type_trans() ate the tag together with the destination MAC. */
	tag = skb->data - ETH_HLEN;

	port = (tag[2] & GSWIP3_SPPID_MASK) >> GSWIP3_SPPID_SHIFT;
	skb->dev = dsa_master_find_slave(dev, 0, port);
	if (!skb->dev)
		return NULL;

	skb_pull_rcsum(skb, GSWIP3_HEADER_LEN);

	return skb;
}

static const struct dsa_device_ops gswip3_netdev_ops = {
	.name		= GSWIP3_NAME,
	.proto		= DSA_TAG_PROTO_GSWIP3,
	.xmit		= gswip3_tag_xmit,
	.rcv		= gswip3_tag_rcv,
	.overhead	= GSWIP3_HEADER_LEN,
};

MODULE_LICENSE("GPL");
MODULE_ALIAS_DSA_TAG_DRIVER(DSA_TAG_PROTO_GSWIP3);

module_dsa_tag_driver(gswip3_netdev_ops);
EOF
echo "tag_gswip3.c escrito"

# ---------- 3. Kconfig + Makefile ----------
grep -q "NET_DSA_TAG_GSWIP3" "$K/net/dsa/Kconfig" || cat >> "$K/net/dsa/Kconfig" <<'EOF'

config NET_DSA_TAG_GSWIP3
	tristate "Tag driver for Lantiq / Intel GSWIP 3.0 switches"
	help
	  Say Y or M if you want to add support for tagging Ethernet frames
	  with the Lantiq / Intel GSWIP 3.0 switch found on the XRX500 SoC.
EOF
grep -q "tag_gswip3" "$K/net/dsa/Makefile" || \
	echo 'obj-$(CONFIG_NET_DSA_TAG_GSWIP3) += tag_gswip3.o' >> "$K/net/dsa/Makefile"

# ---------- 4. el switch usa el tag nuevo ----------
python3 - <<'PY'
p = "/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/lantiq_gswip_xrx500.c"
s = open(p).read()
n = s.count(".tag_protocol = DSA_TAG_PROTO_GSWIP,")
s = s.replace(".tag_protocol = DSA_TAG_PROTO_GSWIP,",
              ".tag_protocol = DSA_TAG_PROTO_GSWIP3,")
open(p, "w").write(s)
print("tag_protocol cambiados:", n)
PY

# ---------- 5. el driver pide el tag ----------
python3 - <<'PY'
import os, glob
for p in glob.glob("/opt/ros-port/linux-5.6.3/drivers/net/dsa/xr/Kconfig"):
    s = open(p).read()
    if "NET_DSA_TAG_GSWIP3" in s:
        print("select ya estaba")
    else:
        s = s.replace("config NET_DSA_XR_GSWIP\n",
                      "config NET_DSA_XR_GSWIP\n\tselect NET_DSA_TAG_GSWIP3\n\tselect NET_DSA_TAG_GSWIP\n", 1)
        open(p, "w").write(s)
        print("select anadido")
PY

echo "== hecho =="
grep -n "NET_DSA_TAG_GSWIP3" "$K/net/dsa/Makefile" "$K/drivers/net/dsa/xr/Kconfig" 2>/dev/null
