#!/bin/bash
K=/opt/ros-port/linux-5.6.3
cd "$K" || exit 1
for c in XFRM INET6_XFRM_TUNNEL JUMP_LABEL USER_NS SKB_EXTENSIONS \
         XFRM_USER NET_KEY XFRM_IPCOMP INET_ESP INET6_ESP; do
    printf '%-24s ' "$c"
    grep -E "^(CONFIG_${c}=|# CONFIG_${c} is not set)" .config || echo "(sin entrada)"
done
echo
echo "=== simbolos en vmlinux ==="
for s in xfrm_lookup xfrm6_tunnel_register static_key_slow_inc __skb_ext_del \
         static_key_disable make_kuid; do
    printf '%-28s ' "$s"
    if nm vmlinux | grep -qE " [A-Za-z] $s\$"; then echo SI; else echo NO; fi
done
