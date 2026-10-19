#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Consistency between marker segment fields (ISO/IEC 15444-1 A.5.1, A.5.2,
A.6.3, A.6.6, A.9.1)."""

import os
import struct

import pytest

from jpylyzer.csmarkers import CSMarkerValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

SIZ_FIELDS = ["xsiz", "ysiz", "xOsiz", "yOsiz", "xTsiz", "yTsiz", "xTOsiz", "yTOsiz"]


def results(marker, contents, csiz=3):
    result = CSMarkerValidator(OPTIONS, marker, contents, components=csiz).validate()
    return {elt.tag: elt.text for elt in result.tests}


def siz(**fields):
    """balloon's SIZ segment with some of the eight geometry fields replaced."""
    data = open(BALLOON, "rb").read()
    offset = data.find(b'\xff\x51')
    lsiz, = struct.unpack(">H", data[offset + 2:offset + 4])
    contents = bytearray(data[offset + 2:offset + 2 + lsiz])
    values = list(struct.unpack(">8I", contents[4:36]))
    for name, value in fields.items():
        values[SIZ_FIELDS.index(name)] = value
    contents[4:36] = struct.pack(">8I", *values)
    return bytes(contents)


@pytest.mark.parametrize("fields,test,expected", [
    ({}, "imageAreaIsValid", True),
    ({"xOsiz": 5000, "xTOsiz": 5000}, "imageAreaIsValid", False),
    ({"yOsiz": 3701, "yTOsiz": 3701}, "imageAreaIsValid", False),
    ({}, "tileOffsetIsValid", True),
    ({"xOsiz": 10, "xTOsiz": 11}, "tileOffsetIsValid", False),
    ({}, "firstTileOverlapsImageArea", True),
    ({"xOsiz": 2000, "xTsiz": 1000}, "firstTileOverlapsImageArea", False),
    ({"yOsiz": 1000, "yTsiz": 1000}, "firstTileOverlapsImageArea", False),
])
def test_siz_geometry(fields, test, expected):
    assert results(b'\xff\x51', siz(**fields))[test] is expected


def segment(fields):
    return struct.pack(">H", len(fields) + 2) + fields


@pytest.mark.parametrize("fields,csiz,expected", [
    (bytes([0, 0, 3]), 3, True),           # Crgn (1 byte), Srgn, SPrgn
    (struct.pack(">HBB", 0, 0, 3), 300, True),
    (struct.pack(">HBB", 0, 0, 3), 3, False),
    (bytes([0, 0, 3]), 300, False),
])
def test_rgn_length(fields, csiz, expected):
    assert results(b'\xff\x5e', segment(fields), csiz)["lrgnIsValid"] is expected


def poc_change(csiz):
    component = (lambda c: bytes([c])) if csiz < 257 else (lambda c: struct.pack(">H", c))
    return bytes([0]) + component(0) + struct.pack(">H", 1) + bytes([1]) + component(1) + \
        bytes([0])


@pytest.mark.parametrize("csiz,changes,extra,expected", [
    (3, 1, b"", True),
    (3, 3, b"", True),
    (300, 2, b"", True),
    (3, 1, b"\x00", False),     # trailing byte
    (3, 0, b"", False),         # no progression order change
])
def test_poc_length(csiz, changes, extra, expected):
    contents = segment(poc_change(csiz) * changes + extra)
    assert results(b'\xff\x5f', contents, csiz)["lpocIsValid"] is expected


@pytest.mark.parametrize("pairs,csiz,expected", [(3, 3, True), (2, 3, False), (4, 3, False)])
def test_crg_length(pairs, csiz, expected):
    contents = segment(struct.pack(">HH", 0, 0) * pairs)
    assert results(b'\xff\x63', contents, csiz)["lcrgIsValid"] is expected


def test_cap_with_part_15():
    # Pcap bit for part 15 (MSB is part 1), one Ccap value
    contents = segment(struct.pack(">IH", 1 << (32 - 15), 0))
    result = CSMarkerValidator(OPTIONS, b'\xff\x50', contents).validate()
    assert result.tests.findtext("lcapIsValid") is True
    assert [e.text for e in result.characteristics.findall("pcapPart")] == [15]


def test_cap_with_truncated_pcap():
    result = CSMarkerValidator(OPTIONS, b'\xff\x50', struct.pack(">H", 8) + b"\x00").validate()
    assert result.tests.findtext("lcapIsValid") is False
    assert result.characteristics.findall("pcapPart") == []
