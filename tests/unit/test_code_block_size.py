#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Code-block width and height in COD and COC (ISO/IEC 15444-1 A.6.1, A.6.2):
2 ** (stored exponent offset + 2), reported as an integer."""

import struct

import pytest

from jpylyzer.csmarkers import CSMarkerValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

COD, COC = b'\xff\x52', b'\xff\x53'
# Scod, SGcod (progression, layers, MCT); Scoc + Ccoc for COC
HEADERS = {COD: bytes([0, 0, 0, 1, 0]), COC: bytes([0, 0])}


def code_block_size(marker, spcod):
    fields = HEADERS[marker] + spcod
    contents = struct.pack(">H", len(fields) + 2) + fields
    result = CSMarkerValidator(OPTIONS, marker, contents, components=3).validate()
    c = result.characteristics
    return c.findtext("codeBlockWidth"), c.findtext("codeBlockHeight")


@pytest.mark.parametrize("marker", [COD, COC])
def test_code_block_size(marker):
    # 5 levels, code-block exponent offsets 4 and 3 (64 x 32), style, transform
    assert code_block_size(marker, bytes([5, 4, 3, 0, 1])) == (64, 32)


@pytest.mark.parametrize("marker", [COD, COC])
def test_truncated_segment(marker):
    # Only the number of decomposition levels is present
    assert code_block_size(marker, bytes([5])) == (-9999, -9999)


@pytest.mark.parametrize("marker", [COD, COC])
@pytest.mark.parametrize("offsets,expected", [((8, 8), (1024, 1024)),
                                              ((9, 0), (-9999, 4)),
                                              ((255, 255), (-9999, -9999))])
def test_exponent_out_of_range(marker, offsets, expected):
    # Exponent offsets 0-8 give the allowed exponents 2-10
    assert code_block_size(marker, bytes([5, *offsets, 0, 1])) == expected
