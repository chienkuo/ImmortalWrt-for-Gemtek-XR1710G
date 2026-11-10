#!/usr/bin/env python3
"""Extract the rootfs payload from an OpenWrt FIT (itb) image.

Handles both in-band data and the external-static layout produced by
"fit ... external-static-with-rootfs" (data-position/data-size properties,
payload appended after the 4k FIT header).  Writes the raw filesystem
image (squashfs) to the output path.

usage: fit-extract-rootfs.py <image.itb> <out.img>
"""
import struct
import sys


def parse_fdt(buf):
    (magic, total, off_struct, off_strings, off_rsv, ver, lcomp, boot,
     sz_str, sz_st) = struct.unpack(">10I", buf[:40])
    if magic != 0xD00DFEED:
        raise ValueError("not a FIT/FDT image")
    strings = buf[off_strings:off_strings + sz_str]

    def name_at(o):
        return strings[o:strings.index(b"\0", o)].decode()

    nodes = {}
    path = []
    i = 0
    while i + 4 <= sz_st:
        tok = struct.unpack(">I", buf[off_struct + i:off_struct + i + 4])[0]
        i += 4
        if tok == 0x00:
            continue
        if tok == 0x01:  # BEGIN_NODE
            j = buf.index(b"\0", off_struct + i)
            nm = buf[off_struct + i:j].decode()
            i = j - off_struct + 1
            i = (i + 3) & ~3
            path.append(nm)
            nodes.setdefault("/".join(path), {})
        elif tok == 0x02:  # END_NODE
            path.pop()
        elif tok == 0x03:  # PROP
            ln, no = struct.unpack(">II", buf[off_struct + i:off_struct + i + 8])
            i += 8
            data = buf[off_struct + i:off_struct + i + ln]
            i += (ln + 3) & ~3
            nodes["/".join(path)][name_at(no)] = data
        elif tok == 0x09:  # END
            break
    return nodes


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    itb, out = sys.argv[1], sys.argv[2]
    data = open(itb, "rb").read()
    nodes = parse_fdt(data)
    for node, props in nodes.items():
        parts = node.split("/")
        if len(parts) != 3 or parts[1] != "images":
            continue
        typ = props.get("type", b"").rstrip(b"\0").decode()
        if typ not in ("filesystem", "multi"):
            continue
        blob = None
        if "data" in props:
            blob = props["data"]
        elif "data-raw" in props:
            blob = props["data-raw"]
        elif "data-position" in props and "data-size" in props:
            pos = struct.unpack(">I", props["data-position"])[0]
            size = struct.unpack(">I", props["data-size"])[0]
            blob = data[pos:pos + size]
        elif "data-offset" in props and "data-size" in props:
            # data-offset counts from the end of the FIT header region
            off = struct.unpack(">I", props["data-offset"])[0]
            size = struct.unpack(">I", props["data-size"])[0]
            blob = data[len(data) - off - size:len(data) - off]
        if blob and blob[:4] == b"hsqs":
            open(out, "wb").write(blob)
            print(f"extracted {len(blob)} bytes squashfs from {node}")
            return 0
    print("no squashfs rootfs sub-image found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
