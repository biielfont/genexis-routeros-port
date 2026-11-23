// SPDX-License-Identifier: GPL-2.0
/*
 * Intel SSO LED driver for the Genexis Pure ED500 (GRX350).
 *
 * The SSO block owns 16 LED outputs.  Ethernet LEDs are driven by the GPHY
 * through the SSO hardware-trigger bits; the front-panel LEDs are driven by
 * software through the per-pin duty-cycle registers.
 *
 * This is a reduced port of the Iopsys leds-intel-sso driver.  It deliberately
 * does not depend on the SSO GPIO driver: the only thing the LEDs need is the
 * SSO register window, so the node is its own syscon and the output-enable bit
 * is written directly.
 */

#include <linux/bitops.h>
#include <linux/clk.h>
#include <linux/leds.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/property.h>
#include <linux/regmap.h>

#define SSO_DUTY_CYCLE(pin)	(0x08 + ((pin) * 4))
#define SSO_CON0		0x2b0
#define SSO_CON1		0x2b4
#define SSO_CPU			0x2b8
#define SSO_CON2		0x2c4
#define SSO_CON3		0x2c8

#define SSO_CON0_RZFL		BIT(26)
#define SSO_CON0_BLINK_R	BIT(30)
#define SSO_CON0_SWU		BIT(31)

#define SSO_MAX_PINS		32
#define SSO_MAX_BRIGHTNESS	255
#define SSO_DEFAULT_BRIGHTNESS	0x80

struct sso_led {
	struct led_classdev cdev;
	struct sso_led_priv *priv;
	u32 pin;
	u32 brightness;
	bool hw_trigger;
};

struct sso_led_priv {
	struct device *dev;
	struct regmap *regmap;
	struct clk *fpid_clk;
	struct clk *sso_clk;
	u32 default_brightness;
	bool falling;
};

static int sso_read_u32(struct fwnode_handle *child, const char *name,
			const char *fallback, u32 *value)
{
	if (!fwnode_property_read_u32(child, name, value))
		return 0;
	if (fallback && !fwnode_property_read_u32(child, fallback, value))
		return 0;
	return -EINVAL;
}

static bool sso_has_prop(struct fwnode_handle *child, const char *name,
			 const char *fallback)
{
	return fwnode_property_present(child, name) ||
	       (fallback && fwnode_property_present(child, fallback));
}

static void sso_set_output(struct sso_led_priv *priv, u32 pin, bool on)
{
	regmap_update_bits(priv->regmap, SSO_CPU, BIT(pin),
			   on ? BIT(pin) : 0);

	/* Software update: latch SSO_CPU into the shift outputs. */
	regmap_update_bits(priv->regmap, SSO_CON0, SSO_CON0_SWU,
			   SSO_CON0_SWU);
}

static void sso_set_hw_trigger(struct sso_led_priv *priv, u32 pin, bool on)
{
	regmap_update_bits(priv->regmap, SSO_CON3, BIT(pin),
			   on ? BIT(pin) : 0);
}

static int sso_hw_init(struct sso_led_priv *priv)
{
	unsigned int pin;

	/* Groups 0 and 1 cover the 16 pins wired on this board. */
	regmap_write(priv->regmap, SSO_CON1, 0x3);
	regmap_write(priv->regmap, SSO_CON2, 0);
	regmap_write(priv->regmap, SSO_CON3, 0);
	regmap_write(priv->regmap, SSO_CPU, 0);

	for (pin = 0; pin < SSO_MAX_PINS; pin++)
		regmap_write(priv->regmap, SSO_DUTY_CYCLE(pin), 0);

	regmap_update_bits(priv->regmap, SSO_CON0, SSO_CON0_RZFL,
			   priv->falling ? SSO_CON0_RZFL : 0);
	/* No hardware blink: brightness is handled by the duty-cycle registers. */
	regmap_update_bits(priv->regmap, SSO_CON0, SSO_CON0_BLINK_R, 0);
	return 0;
}

static void sso_led_brightness_set(struct led_classdev *cdev,
				   enum led_brightness brightness)
{
	struct sso_led *led = container_of(cdev, struct sso_led, cdev);

	led->brightness = brightness;
	regmap_write(led->priv->regmap, SSO_DUTY_CYCLE(led->pin), brightness);

	if (!led->hw_trigger)
		sso_set_output(led->priv, led->pin, brightness != LED_OFF);
}

static enum led_brightness sso_led_brightness_get(struct led_classdev *cdev)
{
	struct sso_led *led = container_of(cdev, struct sso_led, cdev);

	return led->brightness;
}

static int sso_led_probe_child(struct sso_led_priv *priv,
			       struct fwnode_handle *child)
{
	struct sso_led *led;
	const char *label, *trigger = NULL, *state = NULL;
	u32 pin, brightness = priv->default_brightness;
	bool hw_trigger;
	int ret;

	if (fwnode_property_read_string(child, "label", &label)) {
		dev_err(priv->dev, "SSO LED without label\n");
		return -EINVAL;
	}

	if (sso_read_u32(child, "led-pin", "intel,led-pin", &pin) ||
	    pin >= SSO_MAX_PINS) {
		dev_err(priv->dev, "%s: invalid led-pin\n", label);
		return -EINVAL;
	}

	sso_read_u32(child, "sso,brightness", "intel,sso-brightness",
		     &brightness);
	hw_trigger = sso_has_prop(child, "sso,hw-trigger",
				  "intel,sso-hw-trigger");

	fwnode_property_read_string(child, "linux,default-trigger", &trigger);
	if (!fwnode_property_read_string(child, "default-state", &state) &&
	    !strcmp(state, "off"))
		brightness = 0;

	if (brightness > SSO_MAX_BRIGHTNESS)
		brightness = SSO_MAX_BRIGHTNESS;

	led = devm_kzalloc(priv->dev, sizeof(*led), GFP_KERNEL);
	if (!led)
		return -ENOMEM;

	led->priv = priv;
	led->pin = pin;
	led->brightness = brightness;
	led->hw_trigger = hw_trigger;
	led->cdev.name = label;
	led->cdev.default_trigger = trigger;
	led->cdev.brightness_set = sso_led_brightness_set;
	led->cdev.brightness_get = sso_led_brightness_get;
	led->cdev.brightness = brightness;
	led->cdev.max_brightness = SSO_MAX_BRIGHTNESS;

	if (hw_trigger) {
		sso_set_hw_trigger(priv, pin, true);
		regmap_write(priv->regmap, SSO_DUTY_CYCLE(pin), brightness);
	} else {
		regmap_write(priv->regmap, SSO_DUTY_CYCLE(pin), brightness);
		sso_set_output(priv, pin, brightness != 0);
	}

	ret = devm_led_classdev_register(priv->dev, &led->cdev);
	if (ret) {
		dev_err(priv->dev, "failed to register %s: %d\n", label, ret);
		return ret;
	}

	dev_info(priv->dev, "%s: pin %u, %s, brightness %u\n",
		 label, pin, hw_trigger ? "hardware" : "software", brightness);
	return 0;
}

static int sso_led_probe(struct platform_device *pdev)
{
	struct sso_led_priv *priv;
	struct fwnode_handle *child;
	u32 value;
	int ret;

	priv = devm_kzalloc(&pdev->dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	priv->dev = &pdev->dev;
	priv->default_brightness = SSO_DEFAULT_BRIGHTNESS;
	priv->regmap = syscon_node_to_regmap(pdev->dev.of_node);
	if (IS_ERR(priv->regmap)) {
		dev_err(&pdev->dev, "cannot map SSO registers: %ld\n",
			PTR_ERR(priv->regmap));
		return PTR_ERR(priv->regmap);
	}

	if (!sso_read_u32(pdev->dev.fwnode, "sso,default-brightness",
			  "intel,sso-def-brightnes", &value))
		priv->default_brightness = min(value, (u32)SSO_MAX_BRIGHTNESS);

	priv->falling = sso_has_prop(pdev->dev.fwnode, "sso,falling",
				     "intel,sso-falling");

	priv->sso_clk = devm_clk_get(&pdev->dev, "sso");
	if (IS_ERR(priv->sso_clk)) {
		if (PTR_ERR(priv->sso_clk) == -EPROBE_DEFER)
			return -EPROBE_DEFER;
		priv->sso_clk = NULL;
	} else {
		ret = clk_prepare_enable(priv->sso_clk);
		if (ret)
			return ret;
	}

	priv->fpid_clk = devm_clk_get(&pdev->dev, "fpid");
	if (IS_ERR(priv->fpid_clk)) {
		if (PTR_ERR(priv->fpid_clk) == -EPROBE_DEFER) {
			ret = -EPROBE_DEFER;
			goto err_sso_clk;
		}
		priv->fpid_clk = NULL;
	} else {
		ret = clk_prepare_enable(priv->fpid_clk);
		if (ret)
			goto err_sso_clk;
	}

	ret = sso_hw_init(priv);
	if (ret)
		goto err_clk;

	device_for_each_child_node(&pdev->dev, child) {
		ret = sso_led_probe_child(priv, child);
		if (ret)
			break;
	}
	if (ret)
		goto err_clk;

	platform_set_drvdata(pdev, priv);
	return 0;

err_clk:
	if (priv->fpid_clk)
		clk_disable_unprepare(priv->fpid_clk);
err_sso_clk:
	if (priv->sso_clk)
		clk_disable_unprepare(priv->sso_clk);
	return ret;
}

static int sso_led_remove(struct platform_device *pdev)
{
	struct sso_led_priv *priv = platform_get_drvdata(pdev);

	if (priv->fpid_clk)
		clk_disable_unprepare(priv->fpid_clk);
	if (priv->sso_clk)
		clk_disable_unprepare(priv->sso_clk);
	return 0;
}

static const struct of_device_id sso_led_of_match[] = {
	{ .compatible = "intel,sso-led" },
	{ }
};
MODULE_DEVICE_TABLE(of, sso_led_of_match);

static struct platform_driver sso_led_driver = {
	.probe = sso_led_probe,
	.remove = sso_led_remove,
	.driver = {
		.name = "intel-sso-led",
		.of_match_table = sso_led_of_match,
	},
};
module_platform_driver(sso_led_driver);

MODULE_AUTHOR("Intel Corporation");
MODULE_DESCRIPTION("Intel SSO LED driver (Genexis Pure ED500)");
MODULE_LICENSE("GPL v2");
