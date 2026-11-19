#!/usr/bin/env python3
"""Arregla las dos cosas que impiden arrancar el kernel 5.6.3 en el ED500.

1. `fp_nf_changed` en net/netfilter/core.c
   El parche de MikroTik anade ese gancho y solo lo rellena su modulo de
   fastpath. Sin el modulo vale NULL y el kernel salta a la direccion 0 al
   registrar el primer hook netfilter:
       __nf_register_net_hook+0x7c  ("Attempted to kill init!")
   Se protege con `if (fp_nf_changed)`.

2. Bus de regmap del switch en drivers/net/dsa/xr/lantiq_gswip_xrx500.c
   Con el bus "raw" el core de regmap aplica el byteswap de
   val_format_endian, asi que el registro de version devuelve 0x30000000 en
   vez de 0x030 y el probe aborta con "unexpected GSWIP version". Con el bus
   simple (reg_read/reg_write) el valor llega nativo, igual que en 6.18.

3. Registro de version del GSWIP
   El ED500 devuelve la revision 3.0 en el byte alto (0x30000000 en vez de
   0x030), asi que el probe abortaba con -ENODEV. Se normaliza el valor y se
   deja la lectura cruda en el log.

4. `uncached_kernel_address()` en arch/mips/mm/dma-noncoherent.c
   Calcula el alias sin cache como `__pa(addr) + UNCAC_BASE`, que solo vale
   si la RAM empieza en fisico 0. En el ED500 empieza en 512 MiB, asi que el
   resultado se sale de KSEG1 y cae en KSEG2 sin mapear: cualquier
   dma_alloc_coherent revienta (fue el Oops de `ifconfig cbm0 up`).

5. `netdev_register_kobject()` en net/core/net-sysfs.c
   Un parche de MikroTik se salta device_add() para toda interfaz cuyo nombre
   no empiece por eth/wlan/bond/soc..., asi que cbm0 y lan* no aparecen en
   /sys/class/net. DSA busca al maestro justo ahi (of_find_net_device_by_node)
   y devolvia -EPROBE_DEFER para siempre. Se restaura el comportamiento normal.

6. `RESET_LANTIQ` en drivers/reset/Kconfig
   El driver del RCU solo es visible con `SOC_TYPE_XWAY`, y esta placa es
   INTEL_MIPS: olddefconfig borraba el simbolo y el switch abortaba con
   -ENOTSUPP al pedir el reset de las PHY. Se anade INTEL_MIPS al default.

Es idempotente: se puede llamar en cada build.
"""

import os
import sys

RAIZ = "/opt/ros-port/linux-5.6.3"
NETFILTER = RAIZ + "/net/netfilter/core.c"
SWITCH = RAIZ + "/drivers/net/dsa/xr/lantiq_gswip_xrx500.c"
COMMON = RAIZ + "/drivers/net/dsa/xr/lantiq_gswip_common.c"
RESET_KCONFIG = RAIZ + "/drivers/reset/Kconfig"

RESET_VIEJO = "config RESET_LANTIQ\n\tbool \"Lantiq XWAY Reset Driver\" if COMPILE_TEST\n\tdefault SOC_TYPE_XWAY\n"
RESET_NUEVO = "config RESET_LANTIQ\n\tbool \"Lantiq XWAY Reset Driver\" if COMPILE_TEST\n\tdefault SOC_TYPE_XWAY || INTEL_MIPS\n"

BUS_VIEJO = """/* 5.6.3 no tiene reg_shift: las direcciones del XRX500 van desplazadas
 * dos bits, asi que el acceso se hace a mano sobre el bus de regmap.
 */
static int gswip_xrx500_reg_read(void *ctx, const void *reg_buf,
\t\t\t\t size_t reg_len, void *val_buf, size_t val_len)
{
\tu32 reg = get_unaligned_be32(reg_buf);

\t*(u32 *)val_buf = readl((void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}

static int gswip_xrx500_reg_write(void *ctx, const void *data, size_t count)
{
\tconst u8 *d = data;
\tu32 reg = get_unaligned_be32(d);
\tu32 val;

\tmemcpy(&val, d + 4, sizeof(val));
\twritel(val, (void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}

static const struct regmap_bus gswip_xrx500_regmap_bus = {
\t.read = gswip_xrx500_reg_read,
\t.write = gswip_xrx500_reg_write,
};"""

BUS_NUEVO = """/* 5.6.3 no tiene reg_shift: las direcciones del XRX500 van desplazadas
 * dos bits, asi que el acceso se hace a mano. Se usa el bus simple
 * (reg_read/reg_write) y no el raw: con el raw, el core de regmap aplica el
 * byteswap de val_format_endian y el registro de version 3.0 se lee como
 * 0x30000000, con lo que el probe aborta antes de tocar el switch.
 */
static int gswip_xrx500_reg_read(void *ctx, unsigned int reg, unsigned int *val)
{
\t*val = readl((void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}

static int gswip_xrx500_reg_write(void *ctx, unsigned int reg, unsigned int val)
{
\twritel(val, (void __iomem *)ctx + ((unsigned long)reg << 2));
\treturn 0;
}

static const struct regmap_bus gswip_xrx500_regmap_bus = {
\t.reg_read = gswip_xrx500_reg_read,
\t.reg_write = gswip_xrx500_reg_write,
};"""

ENDIAN_VIEJO = "\t.val_format_endian = REGMAP_ENDIAN_LITTLE,\n"
ENDIAN_NUEVO = ""


def parche_netfilter():
    with open(NETFILTER) as f:
        src = f.read()
    if "if (fp_nf_changed)" in src:
        print("netfilter: ya estaba protegido")
        return True

    pares = [
        ("\tfp_nf_changed(1, reg->pf);",
         "\tif (fp_nf_changed)\n\t\tfp_nf_changed(1, reg->pf);"),
        ("\tfp_nf_changed(-1, reg->pf);",
         "\tif (fp_nf_changed)\n\t\tfp_nf_changed(-1, reg->pf);"),
    ]
    for viejo, nuevo in pares:
        n = src.count(viejo)
        if n != 1:
            print(f"netfilter: esperaba 1 ocurrencia de {viejo!r}, hay {n}")
            return False
        src = src.replace(viejo, nuevo)

    with open(NETFILTER, "w") as f:
        f.write(src)
    print("netfilter: fp_nf_changed protegido contra NULL")
    return True


def parche_switch():
    with open(SWITCH) as f:
        src = f.read()

    if BUS_VIEJO in src:
        src = src.replace(BUS_VIEJO, BUS_NUEVO)
        print("switch: bus de regmap pasado a reg_read/reg_write")
    elif BUS_NUEVO in src:
        print("switch: el bus ya estaba bien")
    else:
        print("switch: no encuentro el bloque del bus de regmap")
        return False

    if ENDIAN_VIEJO in src:
        src = src.replace(ENDIAN_VIEJO, ENDIAN_NUEVO, 1)
        print("switch: quitado val_format_endian (bus simple, valor nativo)")
    elif ".val_format_endian" in src:
        print("switch: val_format_endian sigue ahi, revisar a mano")
        return False

    with open(SWITCH, "w") as f:
        f.write(src)
    return True


DMA_NONCOHERENT = RAIZ + "/arch/mips/mm/dma-noncoherent.c"

DMA_VIEJO = "\treturn (void *)(__pa(addr) + UNCAC_BASE);\n"
DMA_NUEVO = (
    "\t/*\n"
    "\t * El alias sin cache esta a (CKSEG1 - CKSEG0) del mapeo directo.\n"
    "\t * Con __pa() + UNCAC_BASE solo cuadra si la RAM empieza en fisico 0;\n"
    "\t * aqui empieza en 512 MiB y el resultado se sale de KSEG1.\n"
    "\t */\n"
    "\treturn (void *)((unsigned long)addr +\n"
    "\t\t\t(UNCAC_BASE - (unsigned long)CKSEG0));\n"
)

DIAG_GPHY_VIEJO = (
    "\terr = gswip_xrx500_gphy_load(chip);\n"
    "\tif (err)\n"
    "\t\treturn err;\n"
)

DIAG_GPHY_NUEVO = (
    "\terr = gswip_xrx500_gphy_load(chip);\n"
    "\tif (err) {\n"
    "\t\tdev_err(dev, \"no he podido arrancar las PHY: %d\\n\", err);\n"
    "\t\treturn err;\n"
    "\t}\n"
)

DIAG_COMMON_VIEJO = (
    "\terr = gswip_probe_common(priv, version);\n"
    "\tif (err)\n"
    "\t\tgoto out_gphy;\n"
)

DIAG_COMMON_NUEVO = (
    "\terr = gswip_probe_common(priv, version);\n"
    "\tif (err) {\n"
    "\t\tdev_err(dev, \"gswip_probe_common fallo: %d\\n\", err);\n"
    "\t\tgoto out_gphy;\n"
    "\t}\n"
)


def parche_dma_uncached():
    with open(DMA_NONCOHERENT) as f:
        src = f.read()

    if "UNCAC_BASE - (unsigned long)CKSEG0" in src:
        print("dma: alias uncached ya corregido")
        return True
    if DMA_VIEJO not in src:
        print("dma: no encuentro el calculo del alias uncached")
        return False

    with open(DMA_NONCOHERENT, "w") as f:
        f.write(src.replace(DMA_VIEJO, DMA_NUEVO, 1))
    print("dma: alias uncached calculado desde CKSEG (RAM en 512 MiB)")
    return True


NET_SYSFS = RAIZ + "/net/core/net-sysfs.c"
MARCA_HOTPLUG = "no need to send hotplug events"


def parche_net_sysfs():
    import re

    with open(NET_SYSFS) as f:
        src = f.read()

    # alta: el parche devuelve 0 antes de device_add()
    src, alta = re.subn(
        r"\t/\* no need to send hotplug events.*?\n\t}\n\n", "", src,
        count=1, flags=re.S)
    # baja: el mismo atajo deja el dispositivo sin borrar
    src, baja = re.subn(
        r"\tif \(strncmp\(ndev->name, \"bond\", 4\).*?\n\t}\n\n", "", src,
        count=1, flags=re.S)

    if alta == 0 and baja == 0:
        print("net-sysfs: ya registra todas las interfaces")
        return True
    if alta == 0:
        print("net-sysfs: no he encontrado el atajo del alta")
        return False

    with open(NET_SYSFS, "w") as f:
        f.write(src)
    print(f"net-sysfs: quitados los atajos del parche (alta={alta}, baja={baja})")
    return True


def parche_diag_probe():
    with open(SWITCH) as f:
        src = f.read()
    cambiado = False

    for viejo, nuevo, marca in (
            (DIAG_GPHY_VIEJO, DIAG_GPHY_NUEVO, "no he podido arrancar las PHY"),
            (DIAG_COMMON_VIEJO, DIAG_COMMON_NUEVO, "gswip_probe_common fallo")):
        if marca in src:
            continue
        if viejo not in src:
            print(f"probe: no encuentro el bloque de {marca}")
            return False
        src = src.replace(viejo, nuevo, 1)
        cambiado = True

    if cambiado:
        with open(SWITCH, "w") as f:
            f.write(src)
        print("probe: fallos de PHY y de la libreria comun ahora se registran")
    else:
        print("probe: ya registra los fallos")
    return True


VERSION_VIEJO = (
    "\terr = regmap_read(priv->gswip, GSWIP_VERSION, &version);\n"
    "\tif (err)\n"
    "\t\treturn err;\n"
    "\n"
    "\tif (version != GSWIP_VERSION_3_0)"
)

VERSION_NUEVO = (
    "\terr = regmap_read(priv->gswip, GSWIP_VERSION, &version);\n"
    "\tif (err)\n"
    "\t\treturn err;\n"
    "\n"
    "\tdev_info(dev, \"registro de version GSWIP: 0x%08x\\n\", version);\n"
    "\n"
    "\t/* El ED500 presenta la revision 3.0 en el byte alto: 0x30000000 en\n"
    "\t * vez de 0x030. Se normaliza antes de comparar y de pasarsela a la\n"
    "\t * libreria comun, que trabaja con el formato corto.\n"
    "\t */\n"
    "\tif (version == (GSWIP_VERSION_3_0 << 24))\n"
    "\t\tversion = GSWIP_VERSION_3_0;\n"
    "\n"
    "\tif (version != GSWIP_VERSION_3_0)"
)


def parche_version():
    with open(SWITCH) as f:
        src = f.read()

    if "registro de version GSWIP" in src:
        print("version: ya esta normalizada")
        return True
    if VERSION_VIEJO not in src:
        print("version: no encuentro el bloque del chequeo")
        return False

    with open(SWITCH, "w") as f:
        f.write(src.replace(VERSION_VIEJO, VERSION_NUEVO, 1))
    print("version: revision 3.0 del byte alto normalizada")
    return True


def parche_reset_kconfig():
    with open(RESET_KCONFIG) as f:
        src = f.read()

    if RESET_NUEVO in src:
        print("reset: RESET_LANTIQ ya es visible en INTEL_MIPS")
        return True
    if RESET_VIEJO not in src:
        print("reset: no encuentro el bloque de RESET_LANTIQ en Kconfig")
        return False

    with open(RESET_KCONFIG, "w") as f:
        f.write(src.replace(RESET_VIEJO, RESET_NUEVO))
    print("reset: RESET_LANTIQ visible tambien en INTEL_MIPS")
    return True


TAG_GSWIP3 = RAIZ + "/net/dsa/tag_gswip3.c"


def parche_tag_cola():
    """La cola del skb le dice al conduit a que puerto va la trama.

    xrx500_cbm_xmit() elige el egreso con skb_get_queue_mapping(): la cola 0
    esta reservada al trafico del stack local, que no lleva cabecera del
    switch, y las demas son una por puerto. El tag de 6.18 marca la cola con
    el indice del puerto y este no lo hacia, asi que todo caia en la cola 0 y
    el CBM lo descartaba en silencio (stats.noport).
    """
    with open(TAG_GSWIP3) as f:
        src = f.read()

    if "skb_set_queue_mapping(skb, dp->index)" in src:
        print("tag: ya marca la cola del puerto")
        return True

    viejo = "\ttag = skb->data;\n"
    nuevo = (
        "\ttag = skb->data;\n\n"
        "\t/* El conduit (CBM) elige el puerto de salida por la cola del skb:\n"
        "\t * la cola 0 es para el trafico local, que no lleva cabecera del\n"
        "\t * switch, y el resto son una cola por puerto.\n"
        "\t */\n"
        "\tskb_set_queue_mapping(skb, dp->index);\n"
    )
    if viejo not in src:
        print("tag: no encuentro 'tag = skb->data;'")
        return False

    with open(TAG_GSWIP3, "w") as f:
        f.write(src.replace(viejo, nuevo, 1))
    print("tag: la cola del skb lleva el puerto (el CBM deja de descartar)")
    return True


def parche_phy_addr():
    """El switch tiene que saber que PHY mira cada puerto.

    dsa_slave_open() llama a port_enable() con dev->phydev. En 5.6 los
    puertos con phy-handle los engancha phylink (phylink_of_phy_connect),
    que no copia el PHY al netdev: dev->phydev es NULL y port_enable deja
    GSWIP_MDIO_PHYp con la direccion 0. El switch termina leyendo el PHY 0
    (el del WAN) y el puerto no mueve ni un paquete aunque su PHY negocie.

    mac_link_up() si recibe el phydev, asi que se programa ahi tambien.
    """
    with open(COMMON) as f:
        src = f.read()

    if "GSWIP_MDIO_PHY_ADDR_MASK,\n\t\t\t\t    phydev->mdio.addr" in src:
        print("phy: la direccion del PHY ya se programa en mac_link_up")
        return True

    viejo = (
        "static void gswip_phylink_mac_link_up(struct dsa_switch *ds, int port,\n"
        "\t\t\t\t     unsigned int mode,\n"
        "\t\t\t\t     phy_interface_t interface,\n"
        "\t\t\t\t     struct phy_device *phydev)\n"
        "{\n"
        "\tstruct gswip_priv *priv = ds->priv;\n"
    )
    nuevo = viejo + (
        "\n"
        "\t/* Con phy-handle el PHY lo engancha phylink y dev->phydev queda\n"
        "\t * NULL, asi que port_enable() programo la direccion 0. Aqui si\n"
        "\t * llega el PHY de verdad.\n"
        "\t */\n"
        "\tif (!dsa_is_cpu_port(ds, port) && phydev)\n"
        "\t\tgswip_mdio_mask_phy(priv, port, GSWIP_MDIO_PHY_ADDR_MASK,\n"
        "\t\t\t\t    phydev->mdio.addr & GSWIP_MDIO_PHY_ADDR_MASK);\n"
    )

    if viejo not in src:
        print("phy: no encuentro el comienzo de gswip_phylink_mac_link_up")
        return False

    with open(COMMON, "w") as f:
        f.write(src.replace(viejo, nuevo, 1))
    print("phy: mac_link_up programa la direccion real del PHY del puerto")
    return True


CBM = RAIZ + "/drivers/net/ethernet/lantiq/xrx500-cbm.c"


def parche_trazas():
    """Trazas de datapath: que cola ve el conduit y que puerto el tag."""
    with open(TAG_GSWIP3) as f:
        tag = f.read()
    with open(CBM) as f:
        cbm = f.read()
    cambiado = False

    if "gswip tag: puerto" not in tag:
        viejo = "\tskb_set_queue_mapping(skb, dp->index);\n"
        nuevo = viejo + (
            "\tpr_info_ratelimited(\"gswip tag: puerto %d cola %u\\n\",\n"
            "\t\t\t    dp->index, skb_get_queue_mapping(skb));\n"
        )
        if viejo not in tag:
            print("trazas: no encuentro el mapeo de cola en el tag")
            return False
        tag = tag.replace(viejo, nuevo, 1)
        cambiado = True

    if "cbm xmit: cola" not in cbm:
        viejo = "\tqueue = skb_get_queue_mapping(skb);\n\tif (queue == XRX500_CBM_TXQ_NONE || queue > priv->eg_num) {\n"
        nuevo = (
            "\tqueue = skb_get_queue_mapping(skb);\n"
            "\tpr_info_ratelimited(\"cbm xmit: cola %u de %u, len %u\\n\",\n"
            "\t\t\t    queue, priv->eg_num, skb->len);\n"
            "\tif (queue == XRX500_CBM_TXQ_NONE || queue > priv->eg_num) {\n"
        )
        if viejo not in cbm:
            print("trazas: no encuentro el arranque de xrx500_cbm_xmit")
            return False
        cbm = cbm.replace(viejo, nuevo, 1)
        cambiado = True

    # Ya cumplieron su funcion (diagnostico del TX): a debug, y asi no
    # inundan la consola ni tapan la salida del init.
    if 'pr_info_ratelimited("gswip tag:' in tag or \
       'pr_info_ratelimited("cbm xmit:' in cbm:
        cambiado = True
    tag = tag.replace('pr_info_ratelimited("gswip tag:',
                      'pr_debug_ratelimited("gswip tag:')
    cbm = cbm.replace('pr_info_ratelimited("cbm xmit:',
                      'pr_debug_ratelimited("cbm xmit:')

    if cambiado:
        with open(TAG_GSWIP3, "w") as f:
            f.write(tag)
        with open(CBM, "w") as f:
            f.write(cbm)
        print("trazas: tag y cbm registran puerto y cola (a debug)")
    else:
        print("trazas: ya puestas")
    return True


def parche_velocidad():
    """mac_link_up pasa UNKNOWN y el driver escribe 0 en el hardware.

    gswip_port_set_speed() no tiene default: con SPEED_UNKNOWN deja
    mdio_phy, mii_cfg y mac_ctrl_0 a 0 y los escribe, o sea SPEED_M10,
    GMII_MII y rate 0. gswip_port_set_duplex() cae en el else y pone
    FDUP_DIS. El MAC acaba a 10M half-duplex mientras el PHY entrega
    1G full: todos los frames llegan con FCS/undersize/align error y
    rx_packets se queda a 0. Usar la velocidad y el duplex reales del
    PHY, y no tocar nada si no se conocen.
    """
    with open(COMMON) as f:
        src = f.read()

    cambios = 0

    viejo_up = (
        "\t\tgswip_port_set_speed(priv, port, SPEED_UNKNOWN, interface);\n"
        "\t\tgswip_port_set_duplex(priv, port, DUPLEX_UNKNOWN);\n"
    )
    nuevo_up = (
        "\t\tgswip_port_set_speed(priv, port,\n"
        "\t\t\t\t     phydev ? phydev->speed : SPEED_UNKNOWN,\n"
        "\t\t\t\t     interface);\n"
        "\t\tgswip_port_set_duplex(priv, port,\n"
        "\t\t\t\t       phydev ? phydev->duplex : DUPLEX_UNKNOWN);\n"
    )
    if viejo_up in src:
        src = src.replace(viejo_up, nuevo_up, 1)
        cambios += 1

    viejo_sp = (
        "\t\tmii_cfg = GSWIP_MII_CFG_RATE_M125;\n"
        "\n"
        "\t\tmac_ctrl_0 = GSWIP_MAC_CTRL_0_GMII_RGMII;\n"
        "\t\tbreak;\n"
        "\t}\n"
    )
    nuevo_sp = (
        "\t\tmii_cfg = GSWIP_MII_CFG_RATE_M125;\n"
        "\n"
        "\t\tmac_ctrl_0 = GSWIP_MAC_CTRL_0_GMII_RGMII;\n"
        "\t\tbreak;\n"
        "\tdefault:\n"
        "\t\t/* velocidad desconocida: dejar el hardware como esta */\n"
        "\t\treturn;\n"
        "\t}\n"
    )
    if viejo_sp in src:
        src = src.replace(viejo_sp, nuevo_sp, 1)
        cambios += 1

    viejo_du = (
        "\t\tmac_ctrl_0 = GSWIP_MAC_CTRL_0_FDUP_EN;\n"
        "\t\tmdio_phy = GSWIP_MDIO_PHY_FDUP_EN;\n"
        "\t} else {\n"
        "\t\tmac_ctrl_0 = GSWIP_MAC_CTRL_0_FDUP_DIS;\n"
        "\t\tmdio_phy = GSWIP_MDIO_PHY_FDUP_DIS;\n"
        "\t}\n"
    )
    nuevo_du = (
        "\t\tmac_ctrl_0 = GSWIP_MAC_CTRL_0_FDUP_EN;\n"
        "\t\tmdio_phy = GSWIP_MDIO_PHY_FDUP_EN;\n"
        "\t} else if (duplex == DUPLEX_HALF) {\n"
        "\t\tmac_ctrl_0 = GSWIP_MAC_CTRL_0_FDUP_DIS;\n"
        "\t\tmdio_phy = GSWIP_MDIO_PHY_FDUP_DIS;\n"
        "\t} else {\n"
        "\t\t/* duplex desconocido: no forzar half */\n"
        "\t\treturn;\n"
        "\t}\n"
    )
    if viejo_du in src:
        src = src.replace(viejo_du, nuevo_du, 1)
        cambios += 1

    if cambios == 0:
        print("velocidad: ya estaba parcheado")
        return True

    with open(COMMON, "w") as f:
        f.write(src)
    print("velocidad: %d tramos parcheados (speed/duplex reales del PHY)" % cambios)
    return cambios == 3


NAND_618 = "/opt/ros-port/linux-6.18/drivers/mtd/nand/raw/lantiq-xrx500-nand.c"
NAND_563 = "/opt/ros-port/linux-5.6.3/drivers/mtd/nand/raw/lantiq-xrx500-nand.c"
NAND_KCONFIG = "/opt/ros-port/linux-5.6.3/drivers/mtd/nand/raw/Kconfig"
NAND_MAKEFILE = "/opt/ros-port/linux-5.6.3/drivers/mtd/nand/raw/Makefile"


DTS_NORRLAND = "/opt/ros-port/linux-5.6.3/arch/mips/boot/dts/intel-mips/norrland.dts"


def parche_nand_dts():
    """El MX30LF1G18AC del ED500 no tiene ECC on-die.

    El dtsi de la familia (seale_avm) declara nand-ecc-mode = "on-die"
    pensando en el MX30LF1GE8AB de la FRITZ. En este chip nand_scan_tail
    cae en NAND_ECC_ON_DIE sin step-size y devuelve -EINVAL, asi que el
    controlador detecta el chip (128 MiB SLC) pero el probe falla. Se
    sobreescribe con BCH por software, que el core de 5.6 trae.
    """
    with open(DTS_NORRLAND) as f:
        src = f.read()

    if "memory@20000000" not in src:
        print("dts: no encuentro el nodo memory en norrland.dts")
        return False

    nodo = (
        "/*\n"
        " * El NAND del ED500 es un Macronix MX30LF1G18AC: SLC de 128 MiB, 2 KiB\n"
        " * de pagina y 64 B de OOB, sin ECC interno. El \"on-die\" que pone el\n"
        " * dtsi de la familia es para el MX30LF1GE8AB de la FRITZ y aqui hace\n"
        " * que nand_scan devuelva -EINVAL. BCH-8 por software: 4 pasos de 512 B\n"
        " * piden 56 B de OOB, caben en los 64.\n"
        " */\n"
        "&nand0 {\n"
        "\tnand-ecc-mode = \"soft\";\n"
        "\tnand-ecc-algo = \"bch\";\n"
        "\tnand-ecc-step-size = <512>;\n"
        "\tnand-ecc-strength = <8>;\n"
        "};\n"
    )

    # Un &nand0 dentro del bloque / { } es un error de sintaxis. Quitar
    # cualquier copia previa (tambien si quedo mal colocada) y dejar una
    # sola al final del fichero, que es donde el dtc la acepta.
    while True:
        idx = src.find("&nand0 {")
        if idx < 0:
            break
        ini = idx
        prev = src.rfind("/*", 0, idx)
        if prev >= 0 and "El NAND del ED500" in src[prev:idx]:
            ini = prev
        fin = src.find("};", idx)
        if fin < 0:
            break
        nl = src.find("\n", fin)
        fin = len(src) if nl < 0 else nl + 1
        src = src[:ini] + src[fin:]

    src = src.rstrip("\n") + "\n\n" + nodo

    with open(DTS_NORRLAND, "w") as f:
        f.write(src)
    print("dts: NAND del ED500 a ECC BCH-8 por software (al final del dts)")
    return True


MTDCORE = "/opt/ros-port/linux-5.6.3/drivers/mtd/mtdcore.c"
MTDBLOCK = "/opt/ros-port/linux-5.6.3/drivers/mtd/mtdblock.c"


MIPS_SETUP = "/opt/ros-port/linux-5.6.3/arch/mips/kernel/setup.c"
LZO_C = "/opt/ros-port/linux-5.6.3/lib/lzo/lzo1x_compress.c"
LZO_D = "/opt/ros-port/linux-5.6.3/lib/lzo/lzo1x_decompress_safe.c"
STUBS_C = "/opt/ros-port/linux-5.6.3/arch/mips/intel-mips/ros_stubs.c"
STUBS_MK = "/opt/ros-port/linux-5.6.3/arch/mips/intel-mips/Makefile"
DRV_BUS = "/opt/ros-port/linux-5.6.3/drivers/base/bus.c"
DRV_PLATFORM = "/opt/ros-port/linux-5.6.3/drivers/base/platform.c"
DRV_CORE = "/opt/ros-port/linux-5.6.3/drivers/base/core.c"

STUBS_SRC = '''// SPDX-License-Identifier: GPL-2.0
/*
 * Stubs de la plataforma RouterBOARD que exigen los modulos de RouterOS.
 *
 * flash.ko se compilo contra el kernel de MikroTik para hardware
 * RouterBOARD y da por hecho que existen estas funciones. En el GRX350 no
 * hay ni EBU SPI ni placa "music": devolver "no hay nada" es la respuesta
 * correcta aqui, y permite que flash.ko cargue y trabaje sobre la API MTD
 * estandar de la NAND del xrx500.
 */
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/spi/spi.h>
#include <linux/types.h>

/* Definida en arch/mips/rb/prom.c, que esta plataforma no compila. */
unsigned long mips_machgroup __read_mostly = 0;
EXPORT_SYMBOL(mips_machgroup);

struct spi_device *rb400_spi_get(void)
{
	return NULL;
}
EXPORT_SYMBOL(rb400_spi_get);

int is_music_lite(void)
{
	return 0;
}
EXPORT_SYMBOL(is_music_lite);

int rb400_spi_sync(struct spi_message *message)
{
	return -ENODEV;
}
EXPORT_SYMBOL(rb400_spi_sync);

int rb400_spiflash_read_verify(unsigned addr, u8 *rdata,
			       const u8 *vdata, unsigned cnt,
			       unsigned addr_size)
{
	return -ENODEV;
}
EXPORT_SYMBOL(rb400_spiflash_read_verify);
'''


def parche_abi_routeros():
    """Completa el ABI que flash.ko y panics.ko de RouterOS esperan.

    Tres cosas distintas:
    - mips_machgroup/mips_machtype no se exportan (y el primero solo existe
      en la plataforma rb).
    - rb400_spi_* e is_music_lite son de la plataforma RouterBOARD; aqui
      van stubs que dicen "no hay hardware", que es la verdad.
    - lzo1x_decompress_safe y lzorle1x_1_compress se exportan GPL-only y
      flash.ko es propietario: el kernel le responde "Unknown symbol".
    """
    cambiado = False

    with open(STUBS_C, "w") as f:
        f.write(STUBS_SRC)
    cambiado = True

    with open(STUBS_MK) as f:
        mk = f.read()
    if "ros_stubs.o" not in mk:
        with open(STUBS_MK, "w") as f:
            f.write(mk.rstrip("\n") + "\nobj-y += ros_stubs.o\n")
        cambiado = True

    with open(MIPS_SETUP) as f:
        setup = f.read()
    if "EXPORT_SYMBOL(mips_machtype)" not in setup:
        viejo = "unsigned long mips_machtype __read_mostly = MACH_UNKNOWN;\n"
        if viejo in setup:
            setup = setup.replace(
                viejo, viejo + "EXPORT_SYMBOL(mips_machtype);\n", 1)
            with open(MIPS_SETUP, "w") as f:
                f.write(setup)
            cambiado = True

    # LZO_COMPRESS no tiene prompt: si nadie lo selecciona, olddefconfig lo
    # apaga. Se pide desde una opcion propia de la plataforma.
    kconf = "/opt/ros-port/linux-5.6.3/arch/mips/intel-mips/Kconfig"
    with open(kconf) as f:
        kc = f.read()
    if "INTEL_MIPS_ROS_ABI" not in kc:
        kc = kc.replace("endif\n", """config INTEL_MIPS_ROS_ABI
\tbool "RouterOS module ABI helpers"
\tdefault y
\thelp
\t  Exporta LZO y los simbolos de la plataforma rb que piden los
\t  modulos propietarios de RouterOS (flash.ko, panics.ko).
\tselect LZO_COMPRESS
\tselect LZO_DECOMPRESS

endif
""", 1)
        with open(kconf, "w") as f:
            f.write(kc)

    # El core de dispositivos exporta tres simbolos que flash.ko usa como
    # GPL-only. Sin ellos el modulo no carga.
    for path, sym in (
        (DRV_BUS, "bus_find_device"),
        (DRV_PLATFORM, "platform_bus_type"),
        (DRV_CORE, "device_match_name"),
    ):
        if not os.path.exists(path):
            continue
        with open(path) as f:
            src = f.read()
        viejo = "EXPORT_SYMBOL_GPL(%s);" % sym
        if viejo in src:
            with open(path, "w") as f:
                f.write(src.replace(viejo, "EXPORT_SYMBOL(%s);" % sym, 1))

    for path in (LZO_C, LZO_D):
        if not os.path.exists(path):
            continue
        with open(path) as f:
            src = f.read()
        nuevo = src.replace("EXPORT_SYMBOL_GPL(", "EXPORT_SYMBOL(")
        if nuevo != src:
            with open(path, "w") as f:
                f.write(nuevo)
            cambiado = True

    print("abi: stubs rb + mips_machtype + lzo exportados")
    return cambiado or True


def parche_mtd_simbolos():
    """Los modulos de RouterOS son propietarios y usan la API MTD.

    El kernel stock exporta mtdcore con EXPORT_SYMBOL_GPL, y un modulo sin
    licencia GPL no ve esos simbolos: flash.ko y panics.ko fallan con
    "Unknown symbol mtd_read_oob (err -2)". El arbol de MikroTik exporta
    esa API sin la restriccion, y es lo que hace falta para que RouterOS
    pueda hablar con la NAND. mtdblock igual, para /dev/mtdblock*.
    """
    total = 0
    for path in (MTDCORE, MTDBLOCK):
        if not os.path.exists(path):
            continue
        with open(path) as f:
            src = f.read()
        n = src.count("EXPORT_SYMBOL_GPL(")
        if n:
            with open(path, "w") as f:
                f.write(src.replace("EXPORT_SYMBOL_GPL(", "EXPORT_SYMBOL("))
        total += n

    if total:
        print("mtd: %d simbolos exportados sin GPL-only" % total)
    else:
        print("mtd: los simbolos ya se exportan sin GPL-only")
    return True


def parche_nand():
    """Porta el controlador EBU NAND del xrx500 desde 6.18.

    El DTS ya trae el nodo (seale_avm.dtsi -> ebu_nand, chip-select 1, ECC
    on-die); en 5.6.3 faltan el driver y CONFIG_MTD. Sin NAND no hay rootfs
    persistente ni forma de flashear el kernel en la placa.
    """
    if not os.path.exists(NAND_618):
        print("nand: no encuentro el driver en el arbol 6.18")
        return False

    with open(NAND_618) as f:
        src = f.read()

    # dev_err_probe() no existe en 5.6.3
    viejo = (
        "\tif (!chip_np)\n"
        "\t\treturn dev_err_probe(dev, -EINVAL,\n"
        "\t\t\t\t     \"missing NAND chip child node\\n\");\n"
    )
    nuevo = (
        "\tif (!chip_np) {\n"
        "\t\tdev_err(dev, \"missing NAND chip child node\\n\");\n"
        "\t\treturn -EINVAL;\n"
        "\t}\n"
    )
    src = src.replace(viejo, nuevo)

    # 5.6.3 no tiene el getter: la tabla se llama nand_ooblayout_lp_ops
    src = src.replace(
        "mtd_set_ooblayout(mtd, nand_get_large_page_ooblayout());",
        "mtd_set_ooblayout(mtd, &nand_ooblayout_lp_ops);",
    )

    # platform_driver.remove devuelve int en 5.6.3
    src = src.replace(
        "static void xrx500_nand_remove(struct platform_device *pdev)",
        "static int xrx500_nand_remove(struct platform_device *pdev)",
    )
    viejo = (
        "\t/* Disable EBU NAND mode so subsequent EBU users see a clean slate. */\n"
        "\twritel(EBU_CON_NANDM_DIS, host->ebu + EBU_CON);\n"
        "}\n"
    )
    nuevo = (
        "\t/* Disable EBU NAND mode so subsequent EBU users see a clean slate. */\n"
        "\twritel(EBU_CON_NANDM_DIS, host->ebu + EBU_CON);\n"
        "\n"
        "\treturn 0;\n"
        "}\n"
    )
    src = src.replace(viejo, nuevo)

    with open(NAND_563, "w") as f:
        f.write(src)

    # Kconfig
    with open(NAND_KCONFIG) as f:
        kc = f.read()
    if "MTD_NAND_LANTIQ_XRX500" not in kc:
        kc += (
            "\nconfig MTD_NAND_LANTIQ_XRX500\n"
            "\tbool \"Lantiq xRX500 (GRX350) EBU NAND controller\"\n"
            "\tdepends on MIPS && OF && HAS_IOMEM\n"
            "\tselect MTD_NAND_CORE\n"
            "\tselect MTD_NAND_ECC_SW_HAMMING\n"
            "\thelp\n"
            "\t  Enables support for NAND Flash chips on the Lantiq / Intel\n"
            "\t  xRX500 (GRX350) family of SoCs, attached to the External Bus\n"
            "\t  Unit (EBU) in legacy NAND mode. Uses the modern exec_op API.\n"
        )
        with open(NAND_KCONFIG, "w") as f:
            f.write(kc)

    # Makefile
    with open(NAND_MAKEFILE) as f:
        mk = f.read()
    if "lantiq-xrx500-nand" not in mk:
        mk += "obj-$(CONFIG_MTD_NAND_LANTIQ_XRX500)\t+= lantiq-xrx500-nand.o\n"
        with open(NAND_MAKEFILE, "w") as f:
            f.write(mk)

    print("nand: driver EBU xrx500 portado y enganchado en Kconfig/Makefile")
    return True


def parche_phylink_ops():
    """Registra las callbacks de phylink que el portado dejo sueltas.

    gswip_phylink_mac_config/link_up/link_down existen en el fichero pero
    gswip_switch_ops solo engancha validate y link_state. Sin link_up el
    switch no se entera nunca de que su PHY ha enlazado: PHY_ADDRp se queda
    en LINK=AUTO y el puerto no recibe ni transmite nada (RMON a cero).
    """
    with open(COMMON) as f:
        src = f.read()

    if ".phylink_mac_link_up\t= gswip_phylink_mac_link_up" in src:
        print("phylink: las callbacks del MAC ya estan registradas")
        return True

    viejo = (
        "\t.phylink_validate\t= gswip_phylink_validate,\n"
        "\t.phylink_mac_link_state\t= gswip_phylink_mac_link_state,\n"
    )
    nuevo = viejo + (
        "\t.phylink_mac_config\t= gswip_phylink_mac_config,\n"
        "\t.phylink_mac_link_down\t= gswip_phylink_mac_link_down,\n"
        "\t.phylink_mac_link_up\t= gswip_phylink_mac_link_up,\n"
    )

    if viejo not in src:
        print("phylink: no encuentro el bloque de ops en gswip_switch_ops")
        return False

    with open(COMMON, "w") as f:
        f.write(src.replace(viejo, nuevo, 1))
    print("phylink: mac_config/link_up/link_down enganchadas al switch")
    return True


def main():
    ok = parche_netfilter()
    ok = parche_switch() and ok
    ok = parche_version() and ok
    ok = parche_dma_uncached() and ok
    ok = parche_net_sysfs() and ok
    ok = parche_diag_probe() and ok
    ok = parche_reset_kconfig() and ok
    ok = parche_tag_cola() and ok
    ok = parche_phy_addr() and ok
    ok = parche_trazas() and ok
    ok = parche_phylink_ops() and ok
    ok = parche_velocidad() and ok
    ok = parche_nand() and ok
    ok = parche_nand_dts() and ok
    ok = parche_mtd_simbolos() and ok
    ok = parche_abi_routeros() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
