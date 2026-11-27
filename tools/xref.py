#!/usr/bin/env python3
"""Busca cadenas en un ELF MIPS y desensambla alrededor de sus referencias.

    python3 tools/xref.py /tmp/rosroot/sbin/sysinit "SCRIPT ERROR: " "userseq"
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mipsdis import secciones, decodifica  # noqa: E402


def info_elf(data):
    e_type = struct.unpack(">H", data[0x10:0x12])[0]
    e_entry = struct.unpack(">I", data[0x18:0x1C])[0]
    e_phoff = struct.unpack(">I", data[0x1C:0x20])[0]
    e_phentsize = struct.unpack(">H", data[0x2A:0x2C])[0]
    e_phnum = struct.unpack(">H", data[0x2C:0x2E])[0]
    print(f"ELF type={e_type} (2=EXEC 3=DYN) entry=0x{e_entry:08x}")
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
            struct.unpack(">8I", data[off:off + 32])
        if p_type in (2, 3, 6):  # DYNAMIC, INTERP, PHDR
            print(f"  phdr type={p_type} off=0x{p_offset:x} vaddr=0x{p_vaddr:x} size=0x{p_filesz:x}")
            if p_type == 3:
                print("   interp:", data[p_offset:p_offset + p_filesz].split(b"\x00")[0])
        if p_type == 2:
            dyn = p_offset
            needed = []
            while True:
                tag, val = struct.unpack(">II", data[dyn:dyn + 8])
                if tag == 0:
                    break
                if tag == 1:  # DT_NEEDED, valor = offset en .dynstr
                    needed.append(val)
                if tag == 5:  # DT_STRTAB vaddr
                    dyn_strtab = val
                dyn += 8
            # localizar dynstr por vaddr en las secciones
            for name, (va, o, sz) in secciones(data).items():
                if name == ".dynstr":
                    for n in needed:
                        end = data.find(b"\x00", o + n)
                        print("   NEEDED:", data[o + n:end].decode("latin-1"))


def va_de(secs, off):
    for n, (va, o, sz) in secs.items():
        if va and o <= off < o + sz:
            return n, va + (off - o)
    return None, None


def main():
    path = sys.argv[1]
    needles = [a.encode() for a in sys.argv[2:]] or [b"SCRIPT ERROR: "]
    data = open(path, "rb").read()
    secs = secciones(data)
    info_elf(data)
    print("secciones:", {k: (hex(v[0]), hex(v[1]), v[2]) for k, v in secs.items()
                         if k in (".text", ".rodata", ".data", ".got", ".bss")})

    hits = []
    for needle in needles:
        i = 0
        while True:
            i = data.find(needle, i)
            if i < 0:
                break
            n, v = va_de(secs, i)
            hits.append((needle, i, n, v))
            i += 4

    va, off, size = secs[".text"]
    cuerpo = data[off:off + size]
    ws = [(va + i, struct.unpack(">I", cuerpo[i:i + 4])[0])
          for i in range(0, len(cuerpo) - 3, 4)]

    def xrefs(target):
        lo = target & 0xFFFF
        hi = ((target + 0x8000) >> 16) & 0xFFFF
        res = []
        for k, (a, w) in enumerate(ws):
            op = w >> 26
            rs = (w >> 21) & 0x1F
            rt = (w >> 16) & 0x1F
            if op in (0x09, 0x0D, 0x0F) and (w & 0xFFFF) == lo and rt == rs and k > 0:
                a0, w0 = ws[k - 1]
                if (w0 >> 26) == 0x0F and (w0 & 0xFFFF) == hi and ((w0 >> 16) & 0x1F) == rt:
                    res.append(a0)
        return res

    for needle, i, n, v in hits:
        print(f"\n=== {needle!r} @file 0x{i:x} {n} VA {('0x%08x' % v) if v else '?'}")
        print("    ctx:", data[max(0, i - 40):i + 80])
        if v is None:
            continue
        xs = xrefs(v)
        print("    xrefs:", [hex(x) for x in xs])
        for x in xs:
            # quien usa el registro cargado: mirar 60 instrucciones alrededor
            ini = max(va, x - 40 * 4)
            print(f"    --- alrededor de 0x{x:08x} ---")
            for a, w in ws:
                if ini <= a <= x + 80 * 4:
                    nombre, ops = decodifica(w, a)
                    marca = " >>" if a == x else "   "
                    print(f"    {marca} 0x{a:08x}: {w:08x}  {nombre:8s} {ops}")


if __name__ == "__main__":
    main()
