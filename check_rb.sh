#!/bin/bash
K=/opt/ros-port/linux-5.6.3
cd "$K" || exit 1
echo "=== rb400_spi_get ==="
grep -rn "rb400_spi_get" arch/mips/rb drivers/spi --include=*.c --include=*.h | head -5
echo
echo "=== is_music_lite ==="
grep -rn "is_music_lite" arch/mips drivers --include=*.c --include=*.h | head -5
echo
echo "=== rb400_spi_sync / read_verify ==="
grep -rn "rb400_spi_sync\|rb400_spiflash_read_verify" arch/mips drivers --include=*.c --include=*.h | head -6
echo
echo "=== mips_machgroup / mips_machtype ==="
grep -rn "mips_machgroup\|mips_machtype" arch/mips/include arch/mips/kernel --include=*.c --include=*.h | head -8
echo
echo "=== lzo export ==="
grep -rn "EXPORT_SYMBOL" lib/lzo/lzo1x_compress.c lib/lzo/lzo1x_decompress_safe.c | head
echo
echo "=== configs LZO ==="
grep -E "^CONFIG_(LZO|LZ4|ZSTD)" .config
