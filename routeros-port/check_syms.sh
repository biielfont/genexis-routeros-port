#!/bin/bash
cd /opt/ros-port/linux-5.6.3 || exit 1
nm vmlinux > /tmp/syms.txt 2>/dev/null
for s in bus_find_device platform_bus_type device_match_name mips_machgroup \
         lzo1x_decompress_safe lzorle1x_1_compress \
         rb400_spi_get is_music_lite rb400_spi_sync rb400_spiflash_read_verify; do
    printf '%-32s ' "$s"
    if grep -qE " [A-Za-z] $s\$" /tmp/syms.txt; then
        printf 'EN VMLINUX  '
        if grep -qP "\t$s\tvmlinux" Module.symvers; then
            echo "exportado"
        else
            echo "NO exportado"
        fi
    else
        echo "NO existe"
    fi
done
