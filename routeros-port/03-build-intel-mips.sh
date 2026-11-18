#!/bin/bash
# H2a: enganchar intel-mips en Kbuild.platforms y compilar.
set -uo pipefail
KDIR=/opt/ros-port/linux-5.6.3
CROSS=/opt/toolchain/bin/mips-buildroot-linux-gnu-
LOG=/opt/ros-port/build4.log
cd "$KDIR" || exit 1

python3 - "$KDIR/arch/mips/Kbuild.platforms" <<'PY'
import sys
p=sys.argv[1]
s=open(p).read()
if 'platforms += intel-mips' not in s:
    s=s.replace('include $(patsubst', 'platforms += intel-mips\n\ninclude $(patsubst')
    open(p,'w').write(s)
print([l for l in open(p).read().splitlines() if 'intel-mips' in l])
PY

{
  make ARCH=mips CROSS_COMPILE="$CROSS" -j4 vmlinux
  echo "BUILD_EXIT=$?"
  ls -l vmlinux 2>/dev/null
} > "$LOG" 2>&1
