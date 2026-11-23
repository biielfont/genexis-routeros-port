#!/usr/bin/env python3
"""Install the ED500 hardware support into a Linux 5.6.3 kernel tree.

The build tree lives in WSL and is not tracked by this repository, so keep the
sources and the DTS fragment here and copy/patch them before every build.  All
operations are idempotent.
"""
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/ros-port/linux-5.6.3")

FILES = {
    ROOT / "kernel/leds-intel-sso.c": KERNEL / "drivers/leds/leds-intel-sso.c",
    ROOT / "kernel/leds-sk9822.c": KERNEL / "drivers/leds/leds-sk9822.c",
    ROOT / "kernel/ed500-buttons.c": KERNEL / "drivers/gpio/ed500-buttons.c",
    ROOT / "kernel/norrland-ed500.dtsi":
        KERNEL / "arch/mips/boot/dts/intel-mips/norrland-ed500.dtsi",
}

KCONFIG_LEDS = """

config LEDS_INTEL_SSO
\ttristate "LED support for Intel SSO"
\tdepends on OF
\tdepends on LEDS_CLASS
\tselect REGMAP
\thelp
\t  LED outputs of the Intel SSO block on the GRX350.  Used for the
\t  Ethernet and front-panel LEDs of the Genexis Pure ED500.

config LEDS_SK9822
\ttristate "SK9822 RGB LED support"
\tdepends on OF
\tdepends on LEDS_CLASS
\thelp
\t  Bit-banged SK9822 addressable RGB LED, as fitted to the Genexis
\t  Pure ED500 front panel.
"""

KCONFIG_GPIO = """

config GPIO_ED500_BUTTONS
\tbool "Genexis Pure ED500 reset button"
\tdepends on GPIOLIB
\thelp
\t  Polls the physical reset button of the Genexis Pure ED500 and
\t  restarts after a long press.  The port keeps its configuration on
\t  a volatile overlay, so the restart restores factory defaults.
"""

MAKEFILE_LEDS = """
obj-$(CONFIG_LEDS_INTEL_SSO) += leds-intel-sso.o
obj-$(CONFIG_LEDS_SK9822) += leds-sk9822.o
"""

MAKEFILE_GPIO = """
obj-$(CONFIG_GPIO_ED500_BUTTONS) += ed500-buttons.o
"""

DTS_INCLUDE = '#include "norrland-ed500.dtsi"\n'


def append_once(path: Path, marker: str, text: str) -> None:
    data = path.read_text()
    if marker in data:
        print(f"  {path}: already patched")
        return
    if not data.endswith("\n"):
        data += "\n"
    path.write_text(data + text)
    print(f"  {path}: patched")


def patch_pinctrl_equilibrium() -> bool:
    """Make the 5.6.3 Equilibrium driver bind the xrx500 pinctrl node.

    The 5.6.3 source only knows intel,lgm-io.  The xrx500 DTS uses
    intel,pinctrl-xrx500, and without this match the gpio banks never probe.
    The modern tree also routes GPIO requests through pinctrl, which is what
    puts the reset/WPS/SK9822 pads into GPIO mode.
    """
    path = KERNEL / "drivers/pinctrl/pinctrl-equilibrium.c"
    data = path.read_text()
    changed = False

    if '"intel,pinctrl-xrx500"' not in data:
        old = '\t{ .compatible = "intel,lgm-io" },'
        new = old + '\n\t{ .compatible = "intel,pinctrl-xrx500" },'
        if old not in data:
            print(f"{path}: cannot find lgm-io match", file=sys.stderr)
            return False
        data = data.replace(old, new, 1)
        changed = True

    if "gc->request = gpiochip_generic_request;" not in data:
        old = "\tgc->label = gctrl->name;\n"
        new = (old +
               "\tgc->request = gpiochip_generic_request;\n"
               "\tgc->free = gpiochip_generic_free;\n")
        if old not in data:
            print(f"{path}: cannot find gpiochip label", file=sys.stderr)
            return False
        data = data.replace(old, new, 1)
        changed = True

    if not changed:
        print(f"  {path}: already patched")
        return True

    path.write_text(data)
    print(f"  {path}: xrx500 match and pinctrl GPIO requests enabled")
    return True


def patch_intel_xway() -> bool:
    """Use the ED500 LED map instead of the generic XWAY one.

    Stock switch_leds programs LED0 = 1000M, LED1 = 10/100M, both steady.
    The mainline driver instead puts every LED in link10xx + activity mode,
    which makes the green/yellow pair on the ED500 look wrong.
    """
    path = KERNEL / "drivers/net/phy/intel-xway.c"
    data = path.read_text()
    if "Genexis Pure ED500 LED map" in data:
        print(f"  {path}: already patched")
        return True

    data = data.replace("\tu32 ledxh;\n\tu32 ledxl;\n", "", 1)
    new_block = (
        "\t/*\n"
        "\t * Genexis Pure ED500 LED map, from the stock switch_leds script:\n"
        "\t * LED0 = 1000M green, LED1 = 10/100M yellow, no activity blink.\n"
        "\t * Register 0x1b is also set to 0x7f00 by the stock firmware.\n"
        "\t */\n"
        "\tphy_write(phydev, 0x1b, 0x7f00);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LEDCH,\n"
        "\t\t      XWAY_MMD_LEDCH_SBF_F04HZ);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LEDCL, 0);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LED0H,\n"
        "\t\t      XWAY_MMD_LEDxH_CON_LINK1000);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LED0L, 0);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LED1H,\n"
        "\t\t      XWAY_MMD_LEDxH_CON_LINK10X);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LED1L, 0);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LED2H, 0);\n"
        "\tphy_write_mmd(phydev, MDIO_MMD_VEND2, XWAY_MMD_LED2L, 0);\n"
        "\n"
        "\treturn 0;\n"
        "}"
    )
    pattern = re.compile(
        r"\tphy_write_mmd\(phydev, MDIO_MMD_VEND2, XWAY_MMD_LEDCH,.*?\n"
        r"\treturn 0;\n\}",
        re.S,
    )
    data, count = pattern.subn(new_block, data, count=1)
    if count != 1:
        print(f"{path}: cannot locate LED block", file=sys.stderr)
        return False
    path.write_text(data)
    print(f"  {path}: ED500 PHY LED map applied")
    return True


def main() -> int:
    if not (KERNEL / "Makefile").exists():
        print(f"kernel tree not found: {KERNEL}", file=sys.stderr)
        return 1

    for src, dst in FILES.items():
        if not src.exists():
            print(f"missing source: {src}", file=sys.stderr)
            return 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  {src.name} -> {dst}")

    append_once(KERNEL / "drivers/leds/Kconfig", "config LEDS_INTEL_SSO",
                KCONFIG_LEDS)
    append_once(KERNEL / "drivers/leds/Makefile", "leds-intel-sso.o",
                MAKEFILE_LEDS)
    append_once(KERNEL / "drivers/gpio/Kconfig", "config GPIO_ED500_BUTTONS",
                KCONFIG_GPIO)
    append_once(KERNEL / "drivers/gpio/Makefile", "ed500-buttons.o",
                MAKEFILE_GPIO)

    if not patch_pinctrl_equilibrium():
        return 1
    if not patch_intel_xway():
        return 1

    dts = KERNEL / "arch/mips/boot/dts/intel-mips/norrland.dts"
    data = dts.read_text()
    if DTS_INCLUDE.strip() in data:
        print(f"  {dts}: already includes ED500 fragment")
    else:
        needle = '#include "seale_avm.dtsi"'
        if needle not in data:
            print(f"{dts}: missing {needle}", file=sys.stderr)
            return 1
        data = data.replace(needle, needle + "\n" + DTS_INCLUDE.strip(), 1)
        dts.write_text(data)
        print(f"  {dts}: ED500 fragment included")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
