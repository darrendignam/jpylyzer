#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Restricted ICC profiles (ISO/IEC 15444-1 I.5.3.3, METH 2): Monochrome or
Three-Component Matrix-Based, so GRAY or RGB, with the matching tags, and
XYZ as PCS for RGB."""

import struct

import pytest

from jpylyzer.boxes import BoxValidator

COLOUR_BOX = b'\x63\x6f\x6c\x72'
OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}
XYZ = b"XYZ " + bytes(4) + struct.pack(">iii", 63190, 65536, 54061)
CURVE = b"curv" + bytes(4) + struct.pack(">I", 0)
MATRIX_TAGS = [(b"rXYZ", XYZ), (b"gXYZ", XYZ), (b"bXYZ", XYZ),
               (b"rTRC", CURVE), (b"gTRC", CURVE), (b"bTRC", CURVE)]


def icc_profile(colourSpace, connectionSpace, tags):
    tags = [(b"wtpt", XYZ)] + tags
    offset = 128 + 4 + 12 * len(tags)
    table, data = struct.pack(">I", len(tags)), b""
    for signature, body in tags:
        table += signature + struct.pack(">II", offset + len(data), len(body))
        data += body
    header = (struct.pack(">I", 128 + len(table) + len(data)) + b"lcms" +
              bytes([4, 0x30, 0, 0]) + b"scnr" + colourSpace + connectionSpace +
              bytes(12) + b"acspAPPL" + bytes(24) +
              struct.pack(">iii", 63190, 65536, 54061) + b"lcms" + bytes(44))
    return header + table + data


def icc_tests(colourSpace, connectionSpace, tags):
    payload = bytes([2, 0, 0]) + icc_profile(colourSpace, connectionSpace, tags)
    tests = BoxValidator(OPTIONS, COLOUR_BOX, payload).validate().tests
    return {elt.tag: elt.text for elt in tests if elt.tag in
            ("iccPermittedColourSpace", "iccRequiredTagsPresent",
             "iccPermittedConnectionSpace")}


@pytest.mark.parametrize("colourSpace,connectionSpace,tags,expected", [
    (b"RGB ", b"XYZ ", MATRIX_TAGS,
     {"iccPermittedColourSpace": True, "iccRequiredTagsPresent": True,
      "iccPermittedConnectionSpace": True}),
    (b"GRAY", b"XYZ ", [(b"kTRC", CURVE)],
     {"iccPermittedColourSpace": True, "iccRequiredTagsPresent": True}),
    (b"RGB ", b"Lab ", MATRIX_TAGS,
     {"iccPermittedColourSpace": True, "iccRequiredTagsPresent": True,
      "iccPermittedConnectionSpace": False}),
    (b"RGB ", b"XYZ ", MATRIX_TAGS[:3],
     {"iccPermittedColourSpace": True, "iccRequiredTagsPresent": False,
      "iccPermittedConnectionSpace": True}),
    (b"GRAY", b"XYZ ", MATRIX_TAGS,
     {"iccPermittedColourSpace": True, "iccRequiredTagsPresent": False}),
    (b"CMYK", b"Lab ", MATRIX_TAGS,
     {"iccPermittedColourSpace": False, "iccRequiredTagsPresent": True}),
])
def test_restricted_icc_profile(colourSpace, connectionSpace, tags, expected):
    assert icc_tests(colourSpace, connectionSpace, tags) == expected
