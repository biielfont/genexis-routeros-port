#!/usr/bin/env python3
"""Resuelve la PLT de un ELF MIPS o32 y anota las llamadas de un rango de codigo.

    python3 tools/pltmap.py binario --va 0x40461c --fin 0x404944

Estrategia: cada entrada de .rel.plt da el slot del GOT y el nombre.  El stub
correspondiente empieza con `lw $t9, imm($gp)`; despejando gp se obtiene el
mapa direccion-de-stub -> simbolo, y despues cada `jal` del rango se resuelve.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mipsdis import secciones, decodifica  # noqa: E402


def relocs_plt(data, secs):
    out = {}
    for sec in (".rel.plt", ".rela.plt"):
        if sec not in secs:
            continue
        va, off, size = secs[sec]
        paso = 8 if sec == ".rel.plt" else 12
        for i in range(0, size, paso):
            r_off, r_info = struct.unpack(">II", data[off + i:off + i + 8])
            out[r_off] = r_info >> 8
    return out


def dynsyms(data, secs):
    va, off, size = secs[".dynsym"]
    sva, soff, ssize = secs[".dynstr"]
    dstr = data[soff:soff + ssize]
    out = []
    for i in range(0, size, 16):
        name = struct.unpack(">I", data[off + i:off + i + 4])[0]
        end = dstr.find(b"\x00", name)
        out.append(dstr[name:end].decode("latin-1"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--va", type=lambda s: int(s, 0))
    ap.add_argument("--fin", type=lambda s: int(s, 0))
    ap.add_argument("--stubs", action="store_true", help="volcar el mapa PLT")
    args = ap.parse_args()

    data = open(args.fichero, "rb").read()
    secs = secciones(data)
    syms = dynsyms(data, secs)
    relplt = relocs_plt(data, secs)
    nombres = {slot: syms[idx] for slot, idx in relplt.items()}

    # Se recorre TODO el fichero (no solo .text): la PLT vive en el hueco
    # entre .rodata y .data, que no aparece en la tabla de secciones.
    # En este binario el sesgo VA = offset + 0x400000 vale para ese tramo.
    ws = []
    for i in range(0, len(data) - 3, 4):
        n, v = None, None
        for nombre_sec, (sva, soff, ssize) in secs.items():
            if soff <= i < soff + ssize:
                n, v = nombre_sec, sva + (i - soff)
                break
        if v is None and secs[".rodata"][1] + secs[".rodata"][2] <= i < secs[".data"][1]:
            v = i + 0x400000
        if v is None:
            continue
        ws.append((v, struct.unpack(">I", data[i:i + 4])[0]))

    # En este binario cada stub de la PLT es:
    #   lui $t7, hi ; lw $t9, imm($t7) ; jr $t9 ; addiu $t8, $t7, imm
    # es decir, el slot se direcciona en absoluto (no via $gp).
    stubs = {}
    for idx, (a, w) in enumerate(ws):
        if (w >> 26) != 0x0F or ((w >> 16) & 0x1F) != 15:      # lui $t7, hi
            continue
        if idx + 1 >= len(ws):
            continue
        a2, w2 = ws[idx + 1]
        if a2 != a + 4 or (w2 >> 26) != 0x23:
            continue
        if ((w2 >> 21) & 0x1F) != 15 or ((w2 >> 16) & 0x1F) != 25:
            continue
        imm = w2 & 0xFFFF
        if imm & 0x8000:
            imm -= 0x10000
        slot = ((w & 0xFFFF) << 16) + imm
        if slot in nombres:
            stubs[a] = nombres[slot]
    print(f"{len(stubs)} stubs resueltos de {len(nombres)}")
    if args.stubs:
        for a in sorted(stubs):
            print(f"  0x{a:08x} {stubs[a]}")

    if args.va is None:
        return

    fin = args.fin or args.va + 0x400
    print(f"\n--- 0x{args.va:08x}..0x{fin:08x} ---")
    for a, w in ws:
        if not (args.va <= a < fin):
            continue
        nombre, ops = decodifica(w, a)
        extra = ""
        if nombre == "jal":
            destino = int(ops, 16)
            extra = "   <" + stubs.get(destino, "?") + ">"
        print(f"0x{a:08x}: {w:08x}  {nombre:8s} {ops}{extra}")


if __name__ == "__main__":
    main()
