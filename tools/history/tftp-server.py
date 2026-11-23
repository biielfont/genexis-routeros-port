#!/usr/bin/env python3
"""
Servidor TFTP minimo de solo lectura, para arrancar el ED500 por red.

  python3 tftp-server.py [directorio] [--port 69]

Sirve los ficheros de `directorio` (por defecto ./out). Pensado para U-Boot:
solo implementa RRQ (lectura) con bloques de 512 bytes y opciones
blksize/tsize, que es lo que pide el cargador de Genexis.

En Windows, si el puerto 69 esta ocupado por otro TFTP, usa --port 6969 y en
U-Boot:  setenv tftpdstp 6969
"""

import argparse
import os
import socket
import struct
import sys

OP_RRQ, OP_DATA, OP_ACK, OP_ERROR, OP_OACK = 1, 3, 4, 5, 6
BLOCK = 512


def parse_request(pkt):
    # pkt = [opcode 2B] filename \0 key \0 value \0 key \0 value \0 ...
    parts = pkt[2:].split(b"\x00")
    if not parts or not parts[0]:
        return None, {}
    filename = parts[0].decode(errors="replace")
    opts = {}
    rest = parts[1:]
    for i in range(0, len(rest) - 1, 2):
        k = rest[i].decode(errors="replace").lower()
        v = rest[i + 1].decode(errors="replace")
        if k:
            opts[k] = v
    return filename, opts


def send_error(sock, addr, code, msg):
    sock.sendto(struct.pack("!HH", OP_ERROR, code) + msg.encode() + b"\x00", addr)


def serve_file(sock, addr, path, opts):
    blksize = min(int(opts.get("blksize", BLOCK)), 65464)
    with open(path, "rb") as f:
        data = f.read()

    if "tsize" in opts or "blksize" in opts:
        oack = struct.pack("!H", OP_OACK)
        if "blksize" in opts:
            oack += b"blksize\x00" + str(blksize).encode() + b"\x00"
        if "tsize" in opts:
            oack += b"tsize\x00" + str(len(data)).encode() + b"\x00"
        sock.sendto(oack, addr)
        pkt, _ = sock.recvfrom(1024)
        if struct.unpack("!H", pkt[:2])[0] != OP_ACK or struct.unpack("!H", pkt[2:4])[0] != 0:
            return

    block = 1
    offset = 0
    total = len(data)
    while True:
        chunk = data[offset:offset + blksize]
        pkt = struct.pack("!HH", OP_DATA, block & 0xFFFF) + chunk
        for _ in range(6):
            sock.sendto(pkt, addr)
            sock.settimeout(2.0)
            try:
                ack, ack_addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            if ack_addr != addr:
                continue
            if struct.unpack("!H", ack[:2])[0] == OP_ACK and \
               struct.unpack("!H", ack[2:4])[0] == (block & 0xFFFF):
                break
        else:
            print(f"  ! timeout en bloque {block}", flush=True)
            return
        offset += len(chunk)
        block += 1
        if len(chunk) < blksize:
            break
    print(f"  -> {total} bytes enviados", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="out")
    ap.add_argument("--port", type=int, default=69)
    ap.add_argument("--bind", default="0.0.0.0")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit(f"no existe el directorio {root}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((args.bind, args.port))
    except PermissionError:
        sys.exit("hace falta permiso para el puerto 69 (en Linux: sudo, o usa --port 6969)")

    print(f"TFTP escuchando en {args.bind}:{args.port}, sirviendo {root}")
    while True:
        pkt, addr = sock.recvfrom(2048)
        if len(pkt) < 4:
            continue
        op = struct.unpack("!H", pkt[:2])[0]
        if op != OP_RRQ:
            send_error(sock, addr, 4, "solo lectura")
            continue

        name, opts = parse_request(pkt)
        print(f"{addr[0]}:{addr[1]} pide {name} {opts}", flush=True)
        path = os.path.abspath(os.path.join(root, name.lstrip("/")))
        if not path.startswith(root) or not os.path.isfile(path):
            send_error(sock, addr, 1, "no existe")
            continue

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind((args.bind, 0))
        try:
            serve_file(client, addr, path, opts)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {exc}", flush=True)
        finally:
            client.close()


if __name__ == "__main__":
    main()
