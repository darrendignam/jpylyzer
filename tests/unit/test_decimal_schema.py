#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Float properties that Python prints in exponent notation (very small ICC
XYZ values, very large grid resolutions) still conform to the schema."""

import os
import struct

from lxml import etree

from jpylyzer import etpatch as ET
from jpylyzer.jpylyzer import checkOneFile, NS_STRING_2

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")
XSD = os.path.join(SCRIPT_DIR, "..", "..", "xsd", "jpylyzer-v-2-3.xsd")


def schema_errors(result):
    toolInfo = ET.Element("toolInfo")
    toolInfo.appendChildTagWithText("toolName", "jpylyzer")
    toolInfo.appendChildTagWithText("toolVersion", "test")
    body = ET.tostring(toolInfo, "unicode", "xml") + ET.tostring(result, "unicode", "xml")
    report = etree.fromstring(('<jpylyzer xmlns="' + NS_STRING_2 + '">' + body +
                               '</jpylyzer>').encode("utf-8"))
    schema = etree.XMLSchema(etree.parse(XSD))
    schema.validate(report)
    return [str(error) for error in schema.error_log]


def box(boxType, payload):
    return struct.pack(">I", 8 + len(payload)) + boxType + payload


def balloon_with_jp2h(edit):
    """balloon.jp2 with edit(children) applied to the JP2 header box payload."""
    data = open(BALLOON, "rb").read()
    start = data.find(b"jp2h") - 4
    length, = struct.unpack(">I", data[start:start + 4])
    children = edit(data[start + 8:start + length])
    return data[:start] + box(b"jp2h", children) + data[start + length:]


def icc_profile(whitePointZ):
    """Minimal ICC v4 RGB matrix/TRC display profile."""
    desc = b"mluc" + bytes(4) + struct.pack(">II", 1, 12) + b"enUS" + \
        struct.pack(">II", 8, 28) + "tiny".encode("utf-16-be")
    wtpt = b"XYZ " + bytes(4) + struct.pack(">iii", 63190, 65536, whitePointZ)
    column = b"XYZ " + bytes(4) + struct.pack(">iii", 63190, 65536, 54061)
    curve = b"curv" + bytes(4) + struct.pack(">I", 0)
    tags = [(b"desc", desc), (b"wtpt", wtpt)] + \
        [(name, column) for name in (b"rXYZ", b"gXYZ", b"bXYZ")] + \
        [(name, curve) for name in (b"rTRC", b"gTRC", b"bTRC")]
    offset = 128 + 4 + 12 * len(tags)
    table, data = struct.pack(">I", len(tags)), b""
    for signature, body in tags:
        body += bytes(-len(body) % 4)
        table += signature + struct.pack(">II", offset + len(data), len(body))
        data += body
    header = (struct.pack(">I", 128 + len(table) + len(data)) + b"lcms" +
              bytes([4, 0x30, 0, 0]) + b"mntrRGB XYZ " + bytes(12) + b"acspAPPL" +
              bytes(24) + struct.pack(">iii", 63190, 65536, 54061) + b"lcms" + bytes(44))
    return header + table + data


def with_icc(children, profile):
    start = children.find(b"colr") - 4
    length, = struct.unpack(">I", children[start:start + 4])
    return children[:start] + box(b"colr", bytes([2, 0, 0]) + profile) + \
        children[start + length:]


def check(tmp_path, data):
    path = tmp_path / "test.jp2"
    path.write_bytes(data)
    result = checkOneFile(str(path))
    assert result.findtext("statusInfo/success") == "True"
    return result


def test_tiny_icc_white_point(tmp_path):
    # s15Fixed16Number 0x00000001 = 1/65536, rounded to 5 places: 2e-05
    result = check(tmp_path, balloon_with_jp2h(
        lambda children: with_icc(children, icc_profile(whitePointZ=1))))
    assert result.findtext(
        "properties/jp2HeaderBox/colourSpecificationBox/icc/mediaWhitePointZ") == "2e-05"
    assert result.findtext("isValid") == "True"
    assert schema_errors(result) == []


def test_huge_capture_resolution(tmp_path):
    # 65535 / 1 * 10^12 pixels per metre
    resc = struct.pack(">HHHHbb", 65535, 1, 65535, 1, 12, 12)
    result = check(tmp_path, balloon_with_jp2h(
        lambda children: children + box(b"res ", box(b"resc", resc))))
    resolution = "properties/jp2HeaderBox/resolutionBox/captureResolutionBox/"
    assert result.findtext(resolution + "vRescInPixelsPerMeter") == "6.5535e+16"
    assert result.findtext("isValid") == "True"
    assert schema_errors(result) == []
