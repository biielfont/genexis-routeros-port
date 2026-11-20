#!/usr/bin/env python3
"""
Herramienta para el contenedor .y3 del Genexis Pure ED500 (Inteno/Iopsys).

Formato (version 5), cabecera de texto de 1024 bytes al principio del fichero:

    IntenoIopY
    version 5
    integrity MD5SUM
    git <hash>
    board NORRLAND
    chip grx550
    arch all mips_24kc_nomips16
    model NORRLAND
    release GNX-4.3.6.170-R
    customer GNX
    ubifsofs 1024          offset del rootfs (imagen UBIFS)
    ubifs <bytes>          tamano del rootfs
    pkginfoofs <offset>    lista de paquetes, texto
    pkginfo <bytes>
    scrofs <offset>        script de instalacion (0 = no hay)
    scr <bytes>
    sigofs <offset>        firma criptografica (0 = no hay!)
    sig <bytes>
    md5ofs <offset>        md5 en ASCII hex
    md5 32
    size <bytes>

No hay firma: solo un MD5. Eso significa que un .y3 propio, con el mismo
esquema y el MD5 correcto, pasa la comprobacion del update.

Uso:
  python3 08-y3tool.py info   fw.y3
  python3 08-y3tool.py unpack fw.y3 salida/
  python3 08-y3tool.py build  nuevo.y3 --ubifs rootfs.ubifs [--pkginfo pk.txt]
                              [--release "GNX-4.3.6.170-R"] [--git 71b8d1b]
"""

import argparse
import hashlib
import os
import sys

MAGIC = "IntenoIopY"
HEADER_SIZE = 1024
FIELDS = ["version", "integrity", "git", "board", "chip", "arch", "model",
          "release", "customer", "ubifsofs", "ubifs", "pkginfoofs", "pkginfo",
          "scrofs", "scr", "sigofs", "sig", "md5ofs", "md5", "size"]


def parse_header(blob):
    text = blob[:HEADER_SIZE].split(b"\x00")[0].decode(errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != MAGIC:
        raise SystemExit("no es un .y3: falta la magia IntenoIopY")
    hdr = {}
    for line in lines[1:]:
        parts = line.split(None, 1)
        if len(parts) == 2:
            hdr[parts[0]] = parts[1].strip()
    return hdr, text


def as_int(hdr, key):
    try:
        return int(hdr.get(key, "0"))
    except ValueError:
        return 0


def cmd_info(args):
    d = open(args.file, "rb").read()
    hdr, text = parse_header(d)
    print(f"fichero: {args.file}  ({len(d)} bytes)")
    print("--- cabecera ---")
    print(text.rstrip())
    print("--- comprobaciones ---")
    md5ofs, md5len = as_int(hdr, "md5ofs"), as_int(hdr, "md5")
    stored = d[md5ofs:md5ofs + md5len].decode(errors="replace")
    print(f"size declarado      {as_int(hdr,'size')}   real {len(d)}   "
          f"{'OK' if as_int(hdr,'size') == len(d) else 'FALLO'}")
    print(f"md5 guardado        {stored}")
    for name, data in [("todo hasta md5ofs", d[:md5ofs]),
                       ("solo el ubifs", d[as_int(hdr,'ubifsofs'):as_int(hdr,'ubifsofs') + as_int(hdr,'ubifs')])]:
        h = hashlib.md5(data).hexdigest()
        print(f"  md5 {name:18} {h} {'<-- COINCIDE' if h == stored else ''}")
    print(f"firma               {as_int(hdr,'sig')} bytes "
          f"{'(sin firma, solo MD5)' if as_int(hdr,'sig') == 0 else ''}")
    uofs, usz = as_int(hdr, "ubifsofs"), as_int(hdr, "ubifs")
    magic = d[uofs:uofs + 4].hex()
    print(f"ubifs               ofs {uofs} tamano {usz} magia {magic} "
          f"{'(UBIFS little-endian, 0x06101831)' if magic == '31181006' else ''}")


def cmd_unpack(args):
    d = open(args.file, "rb").read()
    hdr, _ = parse_header(d)
    os.makedirs(args.out, exist_ok=True)

    def cut(key_ofs, key_len, name):
        ofs, ln = as_int(hdr, key_ofs), as_int(hdr, key_len)
        if ln <= 0:
            print(f"  {name}: vacio, se omite")
            return
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(d[ofs:ofs + ln])
        print(f"  {name}: {ln} bytes (offset {ofs})")

    print(f"extrayendo {args.file} en {args.out}/")
    cut("ubifsofs", "ubifs", "rootfs.ubifs")
    cut("pkginfoofs", "pkginfo", "pkginfo.txt")
    cut("scrofs", "scr", "install.sh")
    cut("md5ofs", "md5", "md5.txt")


def cmd_build(args):
    ubifs = open(args.ubifs, "rb").read()
    pkginfo = b""
    if args.pkginfo:
        pkginfo = open(args.pkginfo, "rb").read()

    md5len = 32
    off_ubifs = HEADER_SIZE
    off_pkg = off_ubifs + len(ubifs)
    off_scr = off_pkg + len(pkginfo)
    off_sig = off_scr          # sin script ni firma
    off_md5 = off_sig
    total = off_md5 + md5len

    fields = {
        "version": "5",
        "integrity": "MD5SUM",
        "git": args.git,
        "board": args.board,
        "chip": args.chip,
        "arch": args.arch,
        "model": args.model,
        "release": args.release,
        "customer": args.customer,
        "ubifsofs": str(off_ubifs),
        "ubifs": str(len(ubifs)),
        "pkginfoofs": str(off_pkg),
        "pkginfo": str(len(pkginfo)),
        "scrofs": str(off_scr),
        "scr": "0",
        "sigofs": str(off_sig),
        "sig": "0",
        "md5ofs": str(off_md5),
        "md5": str(md5len),
        "size": str(total),
    }

    text = MAGIC + "\n" + "".join(f"{k} {fields[k]}\n" for k in FIELDS)
    raw = text.encode()
    if len(raw) > HEADER_SIZE:
        raise SystemExit("la cabecera no cabe en 1024 bytes")
    header = raw + b"\x00" * (HEADER_SIZE - len(raw))

    body = header + ubifs + pkginfo
    md5 = hashlib.md5(body).hexdigest().encode()
    blob = body + md5
    assert len(blob) == total, (len(blob), total)

    with open(args.out, "wb") as f:
        f.write(blob)
    print(f"escrito {args.out}: {len(blob)} bytes")
    print(f"  rootfs {len(ubifs)} B, pkginfo {len(pkginfo)} B, md5 {md5.decode()}")


def main():
    ap = argparse.ArgumentParser(description="contenedor .y3 de Genexis/Iopsys")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="muestra cabecera y valida el md5")
    p.add_argument("file")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("unpack", help="extrae ubifs/pkginfo/script/md5")
    p.add_argument("file")
    p.add_argument("out")
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser("build", help="construye un .y3 a partir de un ubifs")
    p.add_argument("out")
    p.add_argument("--ubifs", required=True, help="imagen UBIFS del rootfs")
    p.add_argument("--pkginfo", help="lista de paquetes en texto")
    p.add_argument("--release", default="GNX-4.3.6.170-R")
    p.add_argument("--git", default="71b8d1b")
    p.add_argument("--board", default="NORRLAND")
    p.add_argument("--chip", default="grx550")
    p.add_argument("--arch", default="all mips_24kc_nomips16")
    p.add_argument("--model", default="NORRLAND")
    p.add_argument("--customer", default="GNX")
    p.set_defaults(func=cmd_build)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
