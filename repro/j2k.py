"""Minimal JP2 / JPEG 2000 codestream editor used to synthesize repro files.

Parses a JP2 into top-level boxes (jp2h, res and uinf as superboxes) and a
codestream into main header marker segments and tile-parts, so that a test can
change one field and rebuild a file with consistent box lengths and Psot values.
"""
import struct

SUPERBOXES = {b'jp2h', b'res ', b'uinf'}


def parse_boxes(data):
    boxes, offset = [], 0
    while offset < len(data):
        length, = struct.unpack('>I', data[offset:offset + 4])
        boxType = data[offset + 4:offset + 8]
        header = 8
        if length == 1:
            length, = struct.unpack('>Q', data[offset + 8:offset + 16])
            header = 16
        if length == 0:
            length = len(data) - offset
        payload = data[offset + header:offset + length]
        if boxType in SUPERBOXES:
            payload = parse_boxes(payload)
        boxes.append([boxType, payload])
        offset += length
    return boxes


def build_boxes(boxes):
    out = b''
    for boxType, payload in boxes:
        if isinstance(payload, list):
            payload = build_boxes(payload)
        out += struct.pack('>I', 8 + len(payload)) + boxType + payload
    return out


def find_box(boxes, boxType):
    return next(box for box in boxes if box[0] == boxType)


def parse_codestream(cs):
    """Return (main header segments, tile-parts, trailer).

    Segments are [marker, payload] with payload excluding the length field
    (None for SOC). Tile-parts are dicts with sot payload, header segments and
    the packet data that follows SOD.
    """
    main, offset = [[cs[0:2], None]], 2
    while cs[offset:offset + 2] != b'\xff\x90':
        length, = struct.unpack('>H', cs[offset + 2:offset + 4])
        main.append([cs[offset:offset + 2], cs[offset + 4:offset + 2 + length]])
        offset += 2 + length
    tileParts = []
    while cs[offset:offset + 2] == b'\xff\x90':
        start = offset
        sot = cs[offset + 4:offset + 12]
        psot, = struct.unpack('>I', sot[2:6])
        end = start + psot if psot else len(cs) - 2
        offset += 12
        segments = []
        while cs[offset:offset + 2] != b'\xff\x93':
            length, = struct.unpack('>H', cs[offset + 2:offset + 4])
            segments.append([cs[offset:offset + 2], cs[offset + 4:offset + 2 + length]])
            offset += 2 + length
        tileParts.append({'sot': bytearray(sot), 'segments': segments,
                          'data': cs[offset + 2:end]})
        offset = end
    return main, tileParts, cs[offset:]


def segment(marker, payload):
    if payload is None:
        return marker
    return marker + struct.pack('>H', len(payload) + 2) + payload


def build_codestream(main, tileParts, trailer):
    out = b''.join(segment(m, p) for m, p in main)
    for tilePart in tileParts:
        header = b''.join(segment(m, p) for m, p in tilePart['segments'])
        psot = 12 + len(header) + 2 + len(tilePart['data'])
        sot = bytearray(tilePart['sot'])
        sot[2:6] = struct.pack('>I', psot)
        out += segment(b'\xff\x90', bytes(sot)) + header + b'\xff\x93' + tilePart['data']
    return out + trailer


def replace_codestream(boxes, edit):
    """Apply edit(main, tileParts) to the codestream of a parsed JP2."""
    jp2c = find_box(boxes, b'jp2c')
    main, tileParts, trailer = parse_codestream(jp2c[1])
    edit(main, tileParts)
    jp2c[1] = build_codestream(main, tileParts, trailer)
