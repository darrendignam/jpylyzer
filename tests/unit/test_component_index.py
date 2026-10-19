#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""COC, QCC and RGN component indices must refer to an existing component,
0 to Csiz - 1 (ISO/IEC 15444-1 A.6.2, A.6.3, A.6.5). The index is 1 byte
for Csiz < 257 and 2 bytes otherwise."""

import struct

import pytest

from jpylyzer.csmarkers import CSMarkerValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

# Parameters after the component index: COC (Scoc, SPcoc with no precincts),
# QCC (Sqcc + one derived value), RGN (Srgn, SPrgn)
MARKERS = {
    "coc": (b'\xff\x53', bytes([0, 5, 4, 4, 0, 1])),
    "qcc": (b'\xff\x5d', bytes([0x41, 0x48, 0x00])),
    "rgn": (b'\xff\x5e', bytes([0, 3])),
}


def index_is_valid(name, index, csiz):
    marker, parameters = MARKERS[name]
    component = bytes([index]) if csiz < 257 else struct.pack(">H", index)
    fields = component + parameters
    contents = struct.pack(">H", len(fields) + 2) + fields
    result = CSMarkerValidator(OPTIONS, marker, contents, components=csiz).validate()
    return result.tests.findtext(f"c{name}IsValid")


@pytest.mark.parametrize("name", MARKERS)
@pytest.mark.parametrize("index,csiz,expected", [
    (0, 1, True),
    (2, 3, True),
    (3, 3, False),
    (255, 3, False),
    (299, 300, True),
    (300, 300, False),
    (16383, 300, False),
])
def test_component_index(name, index, csiz, expected):
    assert index_is_valid(name, index, csiz) is expected
