#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for the jpylyzer unit tests.

- Paths to the repository's example files and XSD schema.
- Validator options.
- Builders that edit JP2 boxes and codestream marker segments in memory, so a
  test can change one field of balloon.jp2 and get a consistent file back
  (box lengths and Psot values are recomputed).
- Wrapping checkOneFile results in a complete jpylyzer report and validating
  it against the schema.
"""

import functools
import os
import struct

from lxml import etree

from jpylyzer import etpatch as ET
from jpylyzer.jpylyzer import NS_STRING_2, XSI_NS_STRING, LOC_SCHEMA_STRING_2, \
    __version__

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
JPYLYZER_DIR = os.path.normpath(os.path.join(TESTS_DIR, "..", ".."))
EXAMPLE_FILES_DIR = os.path.join(JPYLYZER_DIR, "example_files")
BALLOON = os.path.join(EXAMPLE_FILES_DIR, "balloon.jp2")
XSD_FILE = os.path.join(JPYLYZER_DIR, "xsd", "jpylyzer-v-2-3.xsd")

SUPERBOXES = {b'jp2h', b'res ', b'uinf'}


def validatorOptions(validationFormat='jp2', verboseFlag=True,
                     packetmarkersFlag=False, nullxmlFlag=False):
    """Options dictionary as checkOneFile passes it to the validators."""
    return {'validationFormat': validationFormat, 'verboseFlag': verboseFlag,
            'nullxmlFlag': nullxmlFlag, 'packetmarkersFlag': packetmarkersFlag}


@functools.lru_cache(maxsize=None)
def balloonBytes():
    """Contents of example_files/balloon.jp2."""
    with open(BALLOON, "rb") as f:
        return f.read()


def segmentContents(fields):
    """Marker segment as the marker validators receive it: the length field
    (which counts itself) followed by the fields."""
    return struct.pack(">H", len(fields) + 2) + fields


def parseBoxes(data):
    """Parse JP2 boxes into [boxType, payload] lists; superbox payloads are
    parsed recursively."""
    boxes, offset = [], 0
    while offset < len(data):
        length, = struct.unpack(">I", data[offset:offset + 4])
        boxType = data[offset + 4:offset + 8]
        header = 8
        if length == 1:
            length, = struct.unpack(">Q", data[offset + 8:offset + 16])
            header = 16
        if length == 0:
            length = len(data) - offset
        payload = data[offset + header:offset + length]
        if boxType in SUPERBOXES:
            payload = parseBoxes(payload)
        boxes.append([boxType, payload])
        offset += length
    return boxes


def buildBoxes(boxes):
    """Inverse of parseBoxes, with box lengths recomputed."""
    out = b""
    for boxType, payload in boxes:
        if isinstance(payload, list):
            payload = buildBoxes(payload)
        out += struct.pack(">I", 8 + len(payload)) + boxType + payload
    return out


def findBox(boxes, boxType):
    """First [boxType, payload] entry of the given type."""
    return next(box for box in boxes if box[0] == boxType)


def parseCodestream(codestream):
    """Split a codestream into main header segments, tile-parts and trailer.

    Segments are [marker, parameters] (parameters exclude the length field;
    None for SOC). Tile-parts are dicts with the SOT parameters, header
    segments and the data that follows SOD.
    """
    main, offset = [[codestream[0:2], None]], 2
    while codestream[offset:offset + 2] != b'\xff\x90':
        length, = struct.unpack(">H", codestream[offset + 2:offset + 4])
        main.append([codestream[offset:offset + 2], codestream[offset + 4:offset + 2 + length]])
        offset += 2 + length
    tileParts = []
    while codestream[offset:offset + 2] == b'\xff\x90':
        start = offset
        sot = codestream[offset + 4:offset + 12]
        psot, = struct.unpack(">I", sot[2:6])
        end = start + psot if psot else len(codestream) - 2
        offset += 12
        segments = []
        while codestream[offset:offset + 2] != b'\xff\x93':
            length, = struct.unpack(">H", codestream[offset + 2:offset + 4])
            segments.append([codestream[offset:offset + 2],
                             codestream[offset + 4:offset + 2 + length]])
            offset += 2 + length
        tileParts.append({'sot': bytearray(sot), 'segments': segments,
                          'data': codestream[offset + 2:end]})
        offset = end
    return main, tileParts, codestream[offset:]


def markerSegment(marker, parameters):
    """Marker segment bytes; parameters None for delimiting markers."""
    if parameters is None:
        return marker
    return marker + segmentContents(parameters)


def buildCodestream(main, tileParts, trailer):
    """Inverse of parseCodestream, with Psot recomputed."""
    out = b"".join(markerSegment(marker, parameters) for marker, parameters in main)
    for tilePart in tileParts:
        header = b"".join(markerSegment(m, p) for m, p in tilePart['segments'])
        sot = bytearray(tilePart['sot'])
        sot[2:6] = struct.pack(">I", 12 + len(header) + 2 + len(tilePart['data']))
        out += markerSegment(b'\xff\x90', bytes(sot)) + header + b'\xff\x93' + tilePart['data']
    return out + trailer


def editCodestream(boxes, edit):
    """Apply edit(main, tileParts) to the contiguous codestream box."""
    jp2c = findBox(boxes, b'jp2c')
    main, tileParts, trailer = parseCodestream(jp2c[1])
    edit(main, tileParts)
    jp2c[1] = buildCodestream(main, tileParts, trailer)


def mainHeaderSegment(main, marker):
    """First [marker, parameters] entry of the main header with this marker."""
    return next(segment for segment in main if segment[0] == marker)


def reportDocument(fileElements):
    """Complete jpylyzer report (as checkFiles writes it) for checkOneFile
    results, parsed with lxml."""
    toolInfo = ET.Element('toolInfo')
    toolInfo.appendChildTagWithText("toolName", "jpylyzer")
    toolInfo.appendChildTagWithText("toolVersion", __version__)
    body = "".join(ET.tostring(element, "unicode", "xml")
                   for element in [toolInfo] + list(fileElements))
    document = ('<jpylyzer xmlns="' + NS_STRING_2 + '" xmlns:xsi="' + XSI_NS_STRING +
                '" xsi:schemaLocation="' + LOC_SCHEMA_STRING_2 + '">' + body + '</jpylyzer>')
    return etree.fromstring(document.encode("utf-8"))


@functools.lru_cache(maxsize=None)
def schema():
    """The jpylyzer 2.3 output schema."""
    return etree.XMLSchema(etree.parse(XSD_FILE))


def schemaErrors(fileElements):
    """Schema validation errors for a report of these results (empty if valid)."""
    report = reportDocument(fileElements)
    if schema().validate(report):
        return []
    return [str(error) for error in schema().error_log]
