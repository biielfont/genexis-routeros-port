#!/usr/bin/env python3
"""Desensamblador MIPS32 big-endian minimo, sin dependencias.

El objdump de la toolchain de este proyecto no incluye la arquitectura MIPS,
asi que para mirar binarios de RouterOS (ELF32 MSB, `elf32-big`) se usa esto.

Uso:
    python3 tools/mipsdis.py fichero --va 0x40dc00 --fin 0x40dd00
    python3 tools/mipsdis.py fichero --buscar 0x2b0c      # imm == 0x2b0c
    python3 tools/mipsdis.py fichero --seccion .text --va 0x40dc00 -n 60

Solo cubre el subconjunto que aparece en este port: enteros, ramas, cargas y
saltos. No pretende ser un desensamblador completo.
"""

import argparse
import struct

REGS = ("zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
        "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
        "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
        "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra")


def secciones(data):
    """Devuelve {nombre: (vaddr, offset, size)} leyendo la tabla de secciones."""
    if data[:4] != b"\x7fELF":
        raise SystemExit("no es un ELF")
    if data[5] != 2:
        raise SystemExit("solo big-endian")
    e_shoff = struct.unpack(">I", data[0x20:0x24])[0]
    e_shentsize = struct.unpack(">H", data[0x2e:0x30])[0]
    e_shnum = struct.unpack(">H", data[0x30:0x32])[0]
    e_shstrndx = struct.unpack(">H", data[0x32:0x34])[0]

    def sh(i):
        off = e_shoff + i * e_shentsize
        return struct.unpack(">10I", data[off:off + 40])

    str_off = sh(e_shstrndx)[4]
    out = {}
    for i in range(e_shnum):
        name_off, typ, flags, addr, offset, size = sh(i)[:6]
        fin = data.index(b"\x00", str_off + name_off)
        nombre = data[str_off + name_off:fin].decode("latin-1")
        out[nombre] = (addr, offset, size)
    return out


def _simm(w):
    v = w & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _fmt_reg(i):
    return "$" + REGS[i]


def decodifica(w, pc):
    """Devuelve (mnemonico, texto) para una palabra de 32 bits."""
    op = w >> 26
    rs = (w >> 21) & 0x1F
    rt = (w >> 16) & 0x1F
    rd = (w >> 11) & 0x1F
    sa = (w >> 6) & 0x1F
    fn = w & 0x3F
    imm = w & 0xFFFF
    simm = _simm(w)
    destino = pc + 4 + (simm << 2)

    # saltos y ramas: el operando util es el destino absoluto
    if op == 0x02 or op == 0x03:
        objetivo = ((pc + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
        return ("j" if op == 0x02 else "jal"), f"0x{objetivo:08x}"
    if op in (0x04, 0x05, 0x14, 0x15):
        nombre = {0x04: "beq", 0x05: "bne", 0x14: "beql", 0x15: "bnel"}[op]
        return nombre, f"{_fmt_reg(rs)}, {_fmt_reg(rt)}, 0x{destino:08x}"
    if op in (0x06, 0x07, 0x16, 0x17):
        nombre = {0x06: "blez", 0x07: "bgtz",
                  0x16: "blezl", 0x17: "bgtzl"}[op]
        return nombre, f"{_fmt_reg(rs)}, 0x{destino:08x}"
    if op == 0x01:
        nombre = {0x00: "bltz", 0x01: "bgez", 0x10: "bltzal",
                  0x11: "bgezal"}.get(rt)
        if nombre:
            return nombre, f"{_fmt_reg(rs)}, 0x{destino:08x}"

    if op == 0x00:
        special = {
            0x00: ("sll", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rt)}, {sa}"),
            0x02: ("srl", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rt)}, {sa}"),
            0x03: ("sra", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rt)}, {sa}"),
            0x04: ("sllv", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rt)}, {_fmt_reg(rs)}"),
            0x06: ("srlv", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rt)}, {_fmt_reg(rs)}"),
            0x07: ("srav", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rt)}, {_fmt_reg(rs)}"),
            0x08: ("jr", lambda: _fmt_reg(rs)),
            0x09: ("jalr", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}"),
            0x0A: ("movz", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x0B: ("movn", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x0C: ("syscall", lambda: f"0x{(w >> 6) & 0xFFFFF:05x}"),
            0x0D: ("break", lambda: f"0x{(w >> 6) & 0xFFFFF:05x}"),
            0x0F: ("sync", lambda: f"{sa}"),
            0x10: ("mfhi", lambda: _fmt_reg(rd)),
            0x11: ("mthi", lambda: _fmt_reg(rs)),
            0x12: ("mflo", lambda: _fmt_reg(rd)),
            0x13: ("mtlo", lambda: _fmt_reg(rs)),
            0x18: ("mult", lambda: f"{_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x19: ("multu", lambda: f"{_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x1A: ("div", lambda: f"{_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x1B: ("divu", lambda: f"{_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x20: ("add", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x21: ("addu", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x22: ("sub", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x23: ("subu", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x24: ("and", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x25: ("or", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x26: ("xor", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x27: ("nor", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x2A: ("slt", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
            0x2B: ("sltu", lambda: f"{_fmt_reg(rd)}, {_fmt_reg(rs)}, {_fmt_reg(rt)}"),
        }
        if fn in special:
            nombre, ops = special[fn]
            return nombre, ops()
        if fn == 0x08:
            return "jr", _fmt_reg(rs)
        return "special", f"fn=0x{fn:02x}"

    mem = {0x20: ("lb", 1), 0x21: ("lh", 2), 0x23: ("lw", 4),
           0x24: ("lbu", 1), 0x25: ("lhu", 2), 0x28: ("sb", 1),
           0x29: ("sh", 2), 0x2B: ("sw", 4), 0x31: ("lwc1", 4),
           0x39: ("swc1", 4), 0x30: ("ll", 4), 0x38: ("sc", 4),
           0x22: ("lwl", 4), 0x26: ("lwr", 4), 0x2A: ("swl", 4),
           0x2E: ("swr", 4)}
    if op in mem:
        nombre = mem[op][0]
        return nombre, f"{_fmt_reg(rt)}, {simm}({_fmt_reg(rs)})"

    simple = {
        0x08: ("addi", simm), 0x09: ("addiu", simm),
        0x0A: ("slti", simm), 0x0B: ("sltiu", simm),
        0x0C: ("andi", imm), 0x0D: ("ori", imm), 0x0E: ("xori", imm),
        0x0F: ("lui", imm),
    }
    if op in simple:
        nombre, valor = simple[op]
        return nombre, f"{_fmt_reg(rt)}, {_fmt_reg(rs)}, 0x{valor:x}"
    if op == 0x2F:
        return "cache", f"0x{rt:x}, {simm}({_fmt_reg(rs)})"
    return "dw", f"op=0x{op:02x}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--seccion", default=".text")
    ap.add_argument("--va", type=lambda s: int(s, 0))
    ap.add_argument("--fin", type=lambda s: int(s, 0))
    ap.add_argument("-n", type=int, default=80)
    ap.add_argument("--buscar", type=lambda s: int(s, 0),
                    help="imprime las instrucciones con ese inmediato")
    args = ap.parse_args()

    data = open(args.fichero, "rb").read()
    secs = secciones(data)
    if args.seccion not in secs:
        raise SystemExit("secciones: " + ", ".join(sorted(secs)))
    vaddr, offset, size = secs[args.seccion]
    cuerpo = data[offset:offset + size]

    if args.buscar is not None:
        for i in range(0, len(cuerpo) - 3, 4):
            w = struct.unpack(">I", cuerpo[i:i + 4])[0]
            if (w & 0xFFFF) == args.buscar:
                nombre, ops = decodifica(w, vaddr + i)
                print(f"0x{vaddr + i:08x}: {w:08x}  {nombre:8s} {ops}")
        return 0

    inicio = args.va if args.va is not None else vaddr
    if args.fin is not None:
        fin = args.fin
    else:
        fin = inicio + args.n * 4
    for a in range(inicio, fin, 4):
        i = a - vaddr
        if i < 0 or i + 4 > len(cuerpo):
            continue
        w = struct.unpack(">I", cuerpo[i:i + 4])[0]
        nombre, ops = decodifica(w, a)
        print(f"0x{a:08x}: {w:08x}  {nombre:8s} {ops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
