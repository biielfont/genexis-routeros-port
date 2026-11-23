// SPDX-License-Identifier: GPL-2.0
/*
 * Physical reset button on the Genexis Pure ED500.
 *
 * The board database says the reset key is GPIO0 pin 0, active low, and that
 * the stock firmware requires a 5 s press.  RouterOS keeps its configuration
 * on the volatile /flash overlay in this port, so a restart is a factory
 * reset when the port is booted again by TFTP: sysinit regenerates the
 * default configuration on the next boot.  With the stock U-Boot auto-boot
 * left alone, the board will boot the NAND image instead; arm catch_final.py
 * or uboot_cycle.py before pressing the button.
 */

#include <linux/gpio/consumer.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/property.h>
#include <linux/reboot.h>
#include <linux/workqueue.h>

#define ED500_POLL_MS		100
#define ED500_DEFAULT_HOLD_MS	5000

struct ed500_buttons {
	struct device *dev;
	struct gpio_desc *reset;
	struct delayed_work poll;
	unsigned long pressed_at;
	bool pressed;
	u32 hold_ms;
};

static void ed500_cancel(void *data)
{
	struct ed500_buttons *buttons = data;

	cancel_delayed_work_sync(&buttons->poll);
}

static void ed500_poll(struct work_struct *work)
{
	struct ed500_buttons *buttons =
		container_of(work, struct ed500_buttons, poll.work);
	int pressed;

	pressed = gpiod_get_value_cansleep(buttons->reset);
	if (pressed > 0) {
		if (!buttons->pressed) {
			buttons->pressed = true;
			buttons->pressed_at = jiffies;
			dev_info(buttons->dev, "reset button pressed\n");
		} else if (time_after_eq(jiffies,
					 buttons->pressed_at +
					 msecs_to_jiffies(buttons->hold_ms))) {
			dev_emerg(buttons->dev,
				  "reset button held for %u ms, restarting\n",
				  buttons->hold_ms);
			kernel_restart("ed500-reset");
			return;
		}
	} else if (buttons->pressed) {
		buttons->pressed = false;
		dev_info(buttons->dev, "reset button released\n");
	}

	schedule_delayed_work(&buttons->poll, msecs_to_jiffies(ED500_POLL_MS));
}

static int ed500_buttons_probe(struct platform_device *pdev)
{
	struct ed500_buttons *buttons;
	int ret;

	buttons = devm_kzalloc(&pdev->dev, sizeof(*buttons), GFP_KERNEL);
	if (!buttons)
		return -ENOMEM;

	buttons->dev = &pdev->dev;
	buttons->hold_ms = ED500_DEFAULT_HOLD_MS;
	device_property_read_u32(&pdev->dev, "reset-hold-ms",
				 &buttons->hold_ms);
	if (!buttons->hold_ms)
		buttons->hold_ms = ED500_DEFAULT_HOLD_MS;

	buttons->reset = devm_gpiod_get(&pdev->dev, "reset", GPIOD_IN);
	if (IS_ERR(buttons->reset)) {
		dev_err(&pdev->dev, "cannot get reset GPIO: %ld\n",
			PTR_ERR(buttons->reset));
		return PTR_ERR(buttons->reset);
	}

	INIT_DELAYED_WORK(&buttons->poll, ed500_poll);
	ret = devm_add_action_or_reset(&pdev->dev, ed500_cancel, buttons);
	if (ret)
		return ret;

	platform_set_drvdata(pdev, buttons);
	schedule_delayed_work(&buttons->poll, msecs_to_jiffies(ED500_POLL_MS));

	dev_info(&pdev->dev, "reset button ready (hold %u ms)\n",
		 buttons->hold_ms);
	return 0;
}

static const struct of_device_id ed500_buttons_of_match[] = {
	{ .compatible = "genexis,ed500-buttons" },
	{ }
};
MODULE_DEVICE_TABLE(of, ed500_buttons_of_match);

static struct platform_driver ed500_buttons_driver = {
	.probe = ed500_buttons_probe,
	.driver = {
		.name = "ed500-buttons",
		.of_match_table = ed500_buttons_of_match,
	},
};
module_platform_driver(ed500_buttons_driver);

MODULE_AUTHOR("Genexis Pure ED500 port");
MODULE_DESCRIPTION("Physical reset button for the Genexis Pure ED500");
MODULE_LICENSE("GPL v2");
