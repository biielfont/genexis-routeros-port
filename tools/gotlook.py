#!/usr/bin/env python3
"""Resuelve las llamadas de un .so MIPS PIC: `lw $t9, -N($gp)` -> simbolo.

En estos binarios las llamadas externas se hacen cargando el puntero desde el
GOT con un desplazamiento respecto a `gp`. Sabiendo donde esta el GOT se puede
reconstruir `gp` y traducir cada desplazamiento a la entrada de .rel.dyn, que
lleva el nombre del simbolo.

    python3 tools/gotlook.py ros/rootfs/lib/libumsg.so --funcion 0x75b3c:0x75c04

Como ancla se busca en el GOT un puntero a .rodata (0x80000 por defecto, el
bloque de cadenas de libumsg); con ese slot se calcula gp. Si el ancla no
aparece, se puede pasar --gp a mano.
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mipsdis import decodifica, secciones  # noqa: E402


def dynsyms(data, secs):
    va, off, size = secs[".dynsym"]
    sva, soff, ssize = secs[".dynstr"]
    dstr = data[soff:soff + ssize]
    out = []
    for i in range(0, size, 16):
        name, value, sz, info, other, shndx = struct.unpack(
            ">IIIBBH", data[off + i:off + i + 16])
        end = dstr.find(b"\x00", name)
        out.append((dstr[name:end].decode("latin-1"), value, sz, shndx))
    return out


def relocs(data, secs):
    """{(offset, tipo): nombre} para .rel.dyn y .rel.plt."""
    syms = dynsyms(data, secs)
    out = {}
    for sec in (".rel.dyn", ".rel.plt"):
        if sec not in secs:
            continue
        va, off, size = secs[sec]
        for i in range(0, size, 8):
            r_off, r_info = struct.unpack(">II", data[off + i:off + i + 8])
            tipo = r_info & 0xFF
            rsym = r_info >> 8
            nombre = syms[rsym][0] if rsym < len(syms) else ""
            out[(r_off, tipo)] = nombre
    return out


def buscar_gp(data, secs, ancla):
    """Busca en las secciones writables un puntero a `ancla`."""
    cands = []
    for nombre in (".got", ".data.rel.ro", ".data", ".sdata"):
        if nombre not in secs:
            continue
        va, off, size = secs[nombre]
        for i in range(0, size, 4):
            v = struct.unpack(">I", data[off + i:off + i + 4])[0]
            if v == ancla:
                cands.append((nombre, va + i, va + i + 32720))
    return cands


def simbolo_de(rels, slot):
    """El nombre del simbolo cuya entrada de relocation cae en `slot`."""
    for (roff, tipo), nombre in rels.items():
        if roff == slot:
            return f"{nombre or '?'} (tipo {tipo})"
    return None


def leer_u32(data, secs, vaddr):
    """Lee una palabra de una seccion PROGBITS por su direccion virtual."""
    for va, off, size in secs.values():
        if va and va <= vaddr < va + size:
            f = off + (vaddr - va)
            if f + 4 <= len(data):
                return struct.unpack(">I", data[f:f + 4])[0]
    return None


def simbolo_de_stub(data, secs, syms, vaddr):
    """Los stubs perezosos de MIPS llevan el indice de .dynsym en $t8.

    Secuencia tipica:
        lw   $t9, off($gp)
        move $t7, $ra
        jalr $t9
        li   $t8, <indice>
    """
    for a in range(vaddr, vaddr + 24, 4):
        w = leer_u32(data, secs, a)
        if w is None:
            continue
        op = w >> 26
        rt = (w >> 16) & 0x1F
        if op == 0x09 and rt == 24:          # addiu $t8, $zero, N
            n = w & 0xFFFF
            if n & 0x8000:
                n -= 0x10000
            if 0 <= n < len(syms):
                return syms[n][0]
    return None


def simbolo_en(syms, vaddr):
    """Busca un simbolo definido exactamente en `vaddr`."""
    for nombre, value, _sz, shndx in syms:
        if value == vaddr and shndx != 0:
            return nombre
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--funcion", required=True,
                    help="rango INICIO:FIN en hexadecimal, p.ej. 0x75b3c:0x75c04")
    ap.add_argument("--ancla", type=lambda s: int(s, 0), default=0x80000)
    ap.add_argument("--gp", type=lambda s: int(s, 0))
    args = ap.parse_args()

    data = open(args.fichero, "rb").read()
    secs = secciones(data)
    rels = relocs(data, secs)

    ini, fin = (int(x, 16) for x in args.funcion.split(":"))
    if args.gp:
        gp = args.gp
        print(f"gp forzado: 0x{gp:08x}")
    else:
        cands = buscar_gp(data, secs, args.ancla)
        if not cands:
            raise SystemExit("no he encontrado el ancla en el GOT; usa --gp")
        print("candidatos de gp:")
        for nombre, slot, g in cands:
            print(f"  {nombre} slot 0x{slot:08x}  ->  gp 0x{g:08x}")
        gp = cands[0][2]
        print(f"uso gp 0x{gp:08x}")

    va, off, size = secs[".text"]
    cuerpo = data[off:off + size]
    vistos = set()
    print(f"\nllamadas en 0x{ini:08x}..0x{fin:08x}:")
    for a in range(ini, fin, 4):
        i = a - va
        if i < 0 or i + 4 > len(cuerpo):
            continue
        w = struct.unpack(">I", cuerpo[i:i + 4])[0]
        # lw $t9, imm($gp)  =  op 0x23, rs=28, rt=25
        if (w >> 26) == 0x23 and ((w >> 21) & 0x1F) == 28 \
                and ((w >> 16) & 0x1F) == 25:
            imm = w & 0xFFFF
            if imm & 0x8000:
                imm -= 0x10000
            slot = (gp + imm) & 0xFFFFFFFF
            if slot in vistos:
                continue
            vistos.add(slot)
            nombre = simbolo_de(rels, slot)
            destino = leer_u32(data, secs, slot)
            extra = ""
            if destino:
                syms = dynsyms(data, secs)
                st = simbolo_de_stub(data, secs, syms, destino)
                extra = f" -> 0x{destino:08x}"
                st = st or simbolo_en(syms, destino)
                if st:
                    extra += f" {st}"
            print(f"  0x{a:08x}  gp{imm:+#x}  slot 0x{slot:08x}  "
                  f"{nombre or 'sin relocation'}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
