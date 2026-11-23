// SPDX-License-Identifier: GPL-2.0
/*
 * SK9822 RGB LED on the Genexis Pure ED500 front panel.
 *
 * The stock firmware exposes the LED as
 * /sys/devices/platform/canyon_led/sk9822/led_color and writes an RRGGBB
 * string there.  This driver keeps the same interface so the board database
 * and any existing scripts continue to work.
 *
 * The two GPIOs are bit-banged.  led-gpios order is clock first, data second,
 * matching the stock canyon,led node and the vendor module's probe order.
 */

#include <linux/ctype.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/mm.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/property.h>
#include <linux/slab.h>

#define SK9822_MAX_LEDS		32
#define SK9822_HALF_PERIOD_NS	400
#define SK9822_DEFAULT_BRIGHT	0x1f

struct sk9822_led {
	struct device *dev;
	struct gpio_desc *clk;
	struct gpio_desc *data;
	struct class *class;
	struct device *sysfs_dev;
	struct mutex lock;
	u32 count;
	u8 r, g, b;
};

static void sk9822_send_byte(struct sk9822_led *led, u8 value)
{
	int bit;

	for (bit = 7; bit >= 0; bit--) {
		gpiod_set_value(led->data, (value >> bit) & 1);
		ndelay(SK9822_HALF_PERIOD_NS);
		gpiod_set_value(led->clk, 1);
		ndelay(SK9822_HALF_PERIOD_NS);
		gpiod_set_value(led->clk, 0);
	}
}

static void sk9822_send_frame(struct sk9822_led *led)
{
	u8 header = 0xe0 | SK9822_DEFAULT_BRIGHT;
	int i;

	/* Start frame. */
	for (i = 0; i < 4; i++)
		sk9822_send_byte(led, 0);

	/* SK9822 consumes BGR, then a 5-bit global brightness. */
	for (i = 0; i < led->count; i++) {
		sk9822_send_byte(led, header);
		sk9822_send_byte(led, led->b);
		sk9822_send_byte(led, led->g);
		sk9822_send_byte(led, led->r);
	}

	/* End frame and latch. */
	for (i = 0; i < 4; i++)
		sk9822_send_byte(led, 0xff);
	udelay(100);
}

static int sk9822_set_color(struct sk9822_led *led, u8 r, u8 g, u8 b)
{
	mutex_lock(&led->lock);
	led->r = r;
	led->g = g;
	led->b = b;
	sk9822_send_frame(led);
	mutex_unlock(&led->lock);
	return 0;
}

static ssize_t led_color_show(struct device *dev,
			      struct device_attribute *attr, char *buf)
{
	struct sk9822_led *led = dev_get_drvdata(dev);

	return scnprintf(buf, PAGE_SIZE, "%02x%02x%02x\n",
			 led->r, led->g, led->b);
}

static ssize_t led_color_store(struct device *dev,
			       struct device_attribute *attr,
			       const char *buf, size_t count)
{
	struct sk9822_led *led = dev_get_drvdata(dev);
	unsigned int r, g, b;
	const char *p = buf;

	while (isspace(*p))
		p++;
	if (*p == '#')
		p++;

	if (sscanf(p, "%2x%2x%2x", &r, &g, &b) != 3)
		return -EINVAL;
	if (r > 255 || g > 255 || b > 255)
		return -EINVAL;

	sk9822_set_color(led, r, g, b);
	return count;
}

static DEVICE_ATTR_RW(led_color);

static int sk9822_probe(struct platform_device *pdev)
{
	struct sk9822_led *led;
	int ret;

	led = devm_kzalloc(&pdev->dev, sizeof(*led), GFP_KERNEL);
	if (!led)
		return -ENOMEM;

	led->dev = &pdev->dev;
	mutex_init(&led->lock);

	led->clk = devm_gpiod_get_index(&pdev->dev, "led", 0, GPIOD_OUT_LOW);
	if (IS_ERR(led->clk)) {
		dev_err(&pdev->dev, "cannot get SK9822 clock GPIO: %ld\n",
			PTR_ERR(led->clk));
		return PTR_ERR(led->clk);
	}

	led->data = devm_gpiod_get_index(&pdev->dev, "led", 1, GPIOD_OUT_LOW);
	if (IS_ERR(led->data)) {
		dev_err(&pdev->dev, "cannot get SK9822 data GPIO: %ld\n",
			PTR_ERR(led->data));
		return PTR_ERR(led->data);
	}

	if (device_property_read_u32(&pdev->dev, "led-count", &led->count) ||
	    !led->count)
		led->count = 1;
	if (led->count > SK9822_MAX_LEDS)
		led->count = SK9822_MAX_LEDS;

	led->class = class_create(THIS_MODULE, "canyon_led");
	if (IS_ERR(led->class))
		return PTR_ERR(led->class);

	led->sysfs_dev = device_create(led->class, &pdev->dev, 0, led,
				       "sk9822");
	if (IS_ERR(led->sysfs_dev)) {
		ret = PTR_ERR(led->sysfs_dev);
		goto err_class;
	}

	ret = device_create_file(led->sysfs_dev, &dev_attr_led_color);
	if (ret)
		goto err_device;

	platform_set_drvdata(pdev, led);
	sk9822_set_color(led, 0, 0, 0);

	dev_info(&pdev->dev, "SK9822 ready, %u LED(s), led_color at %s\n",
		 led->count, dev_name(led->sysfs_dev));
	return 0;

err_device:
	device_unregister(led->sysfs_dev);
err_class:
	class_destroy(led->class);
	return ret;
}

static int sk9822_remove(struct platform_device *pdev)
{
	struct sk9822_led *led = platform_get_drvdata(pdev);

	sk9822_set_color(led, 0, 0, 0);
	device_remove_file(led->sysfs_dev, &dev_attr_led_color);
	device_unregister(led->sysfs_dev);
	class_destroy(led->class);
	return 0;
}

static const struct of_device_id sk9822_of_match[] = {
	{ .compatible = "canyon,led" },
	{ }
};
MODULE_DEVICE_TABLE(of, sk9822_of_match);

static struct platform_driver sk9822_driver = {
	.probe = sk9822_probe,
	.remove = sk9822_remove,
	.driver = {
		.name = "canyon-led",
		.of_match_table = sk9822_of_match,
	},
};
module_platform_driver(sk9822_driver);

MODULE_AUTHOR("Genexis / Iopsys");
MODULE_DESCRIPTION("SK9822 front-panel RGB LED (Genexis Pure ED500)");
MODULE_LICENSE("GPL v2");
