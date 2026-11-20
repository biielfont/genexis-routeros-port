# SPDX-License-Identifier: GPL-2.0
dtb-$(CONFIG_DTB_INTEL_MIPS_GRX500)	+= norrland.dtb

obj-$(CONFIG_BUILTIN_DTB)	+= $(addsuffix .o, $(dtb-y))

always		:= $(dtb-y)
clean-files	:= *.dtb *.dtb.S
