#!/bin/bash
cd /opt/ros-port/linux-5.6.3 || exit 1
T=/tmp/initchk
rm -rf $T && mkdir -p $T
cd $T || exit 1
zcat /opt/ros-port/linux-5.6.3/usr/initramfs_data.cpio.gz 2>/dev/null | cpio -id 2>/dev/null
echo "=== ROS_SHELL en el init del cpio ==="
grep -n -E "ROS_SHELL|rosbusybox|shell dentro" init | head -10
echo
echo "=== copia en el arbol ==="
grep -n -E "ROS_SHELL|rosbusybox" /opt/ros-port/initramfs/init | head -10
echo
echo "=== fuente del proyecto ==="
grep -n -E "ROS_SHELL|rosbusybox" /mnt/c/Users/BFR/Documents/Genexis/routeros-port/init-initramfs.sh | head -10
