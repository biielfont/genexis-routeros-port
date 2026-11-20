"""Servidor TFTP minimo de solo lectura, en un hilo, para U-Boot.

Se integra en el cazador para que un solo proceso sirva la imagen y arranque
la placa. Implementa RRQ con opciones blksize/tsize, que es lo que pide el
U-Boot del ED500.
"""

import os
import socket
import struct
import threading

OP_RRQ, OP_DATA, OP_ACK, OP_ERROR, OP_OACK = 1, 3, 4, 5, 6
BLOCK = 512


def _parse_request(pkt):
    parts = pkt[2:].split(b"\x00")
    if not parts or not parts[0]:
        return None, {}
    name = parts[0].decode(errors="replace")
    opts = {}
    rest = parts[1:]
    for i in range(0, len(rest) - 1, 2):
        k = rest[i].decode(errors="replace").lower()
        v = rest[i + 1].decode(errors="replace")
        if k:
            opts[k] = v
    return name, opts


def _serve_file(sock, addr, path, opts, out=print):
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
        if len(pkt) < 4 or struct.unpack("!H", pkt[:2])[0] != OP_ACK or \
                struct.unpack("!H", pkt[2:4])[0] != 0:
            return

    block, offset, total = 1, 0, len(data)
    while True:
        chunk = data[offset:offset + blksize]
        pkt = struct.pack("!HH", OP_DATA, block & 0xFFFF) + chunk
        for _ in range(8):
            sock.sendto(pkt, addr)
            sock.settimeout(2.0)
            try:
                ack, ack_addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            if ack_addr != addr or len(ack) < 4:
                continue
            if struct.unpack("!H", ack[:2])[0] == OP_ACK and \
                    struct.unpack("!H", ack[2:4])[0] == (block & 0xFFFF):
                break
        else:
            out(f"  ! timeout en bloque {block}")
            return
        offset += len(chunk)
        block += 1
        if len(chunk) < blksize:
            break
    out(f"  -> {total} bytes enviados")


def _loop(root, bind, port, out):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    out(f"TFTP escuchando en {bind}:{port}, sirviendo {root}")
    while True:
        pkt, addr = sock.recvfrom(2048)
        if len(pkt) < 4:
            continue
        if struct.unpack("!H", pkt[:2])[0] != OP_RRQ:
            sock.sendto(struct.pack("!HH", OP_ERROR, 4) + b"solo lectura\x00", addr)
            continue
        name, opts = _parse_request(pkt)
        out(f"{addr[0]}:{addr[1]} pide {name} {opts}")
        path = os.path.abspath(os.path.join(root, name.lstrip("/")))
        if not path.startswith(root) or not os.path.isfile(path):
            sock.sendto(struct.pack("!HH", OP_ERROR, 1) + b"no existe\x00", addr)
            continue
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind((bind, 0))
        try:
            _serve_file(client, addr, path, opts, out)
        except Exception as exc:  # noqa: BLE001
            out(f"  ! {exc}")
        finally:
            client.close()


def _try_bind(bind, port):
    """Devuelve True si el puerto queda ocupado por otro (o sea, no es nuestro)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind((bind, port))
        probe.close()
        return False          # libre: nadie lo ocupa
    except OSError:
        return True           # ocupado


def start(root="out", bind="0.0.0.0", ports=(69, 6969), out=print):
    """Arranca el servidor en un hilo daemon.

    Prueba los puertos en orden y devuelve el que ha conseguido, o None.
    Asi no depende de que otro TFTP siga vivo de una sesion anterior.
    """
    import time

    root = os.path.abspath(root)
    for port in ports:
        if _try_bind(bind, port):
            out(f"TFTP: el puerto {port} ya esta ocupado, pruebo el siguiente")
            continue

        def runner(p=port):
            try:
                _loop(root, bind, p, out)
            except OSError as exc:
                out(f"TFTP no pudo escuchar en {p}: {exc}")

        threading.Thread(target=runner, daemon=True).start()
        time.sleep(0.4)
        if _try_bind(bind, port):
            return port
        out(f"TFTP: no he podido quedarme con el puerto {port}")
    return None
