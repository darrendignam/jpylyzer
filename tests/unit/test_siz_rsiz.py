#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""SIZ Rsiz decoding (ISO/IEC 15444-1 A.5.1, Table A.10)."""

import os
import struct

import pytest

from jpylyzer.csmarkers import CSMarkerValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


def balloon_siz_contents():
    """SIZ marker segment of balloon.jp2, from Lsiz onwards."""
    data = open(BALLOON, "rb").read()
    offset = data.find(b'\xff\x51')
    lsiz, = struct.unpack(">H", data[offset + 2:offset + 4])
    return data[offset + 2:offset + 2 + lsiz]


SIZ = balloon_siz_contents()


def capability(rsiz):
    contents = SIZ[:2] + struct.pack(">H", rsiz) + SIZ[4:]
    result = CSMarkerValidator(OPTIONS, b'\xff\x51', contents).validate()
    return result.characteristics.findtext("capability")


@pytest.mark.parametrize("rsiz,expected", [
    (0x0000, "ISO/IEC 15444-1"),
    (0x0007, "Long-term storage profile"),
    (0x0008, "Unknown (value not defined in ISO/IEC 15444-1)"),
    (0x000F, "Unknown (value not defined in ISO/IEC 15444-1)"),
    (0x0723, "2k IMF Single/Multi Tile Reversible Profile, Mainlevel 3; Sublevel 2"),
    (0x0823, "4k IMF Single/Multi Tile Reversible Profile, Mainlevel 3; Sublevel 2"),
    (0x0923, "8k IMF Single/Multi Tile Reversible Profile, Mainlevel 3; Sublevel 2"),
])
def test_capability(rsiz, expected):
    assert capability(rsiz) == expected


def test_every_rsiz_value_is_decoded():
    """No Rsiz value may crash the SIZ validator."""
    for rsiz in range(0x10000):
        assert capability(rsiz), hex(rsiz)
