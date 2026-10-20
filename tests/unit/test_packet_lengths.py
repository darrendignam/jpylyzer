#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Iplt/Iplm parsing (PLT/PLM marker segments, ISO/IEC 15444-1 A.7.2, A.7.3)."""

import os
import struct

import pytest

from jpylyzer.codestream import CSValidator
from jpylyzer.csmarkers import CSMarkerValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

# Unterminated packet lengths once made parsing loop forever
pytestmark = pytest.mark.timeout(10)

OPTIONS = {'validationFormat': 'j2c', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': True}


def validate(marker, contents):
    result = CSMarkerValidator(OPTIONS, marker, contents).validate()
    properties = {elt.tag: elt.text for elt in result.characteristics}
    tests = {elt.tag: elt.text for elt in result.tests}
    return properties, tests


def test_plt_multi_byte_lengths():
    # 0x9F 0x62: continuation bit set on the first byte -> 0x1F << 7 | 0x62
    properties, tests = validate(b'\xff\x58', b'\x00\x07\x00\x0c\x9f\x62\x7c')
    assert properties["iplt"] == "0C,0FE2,7C"
    assert tests["ipltIsValid"] is True


@pytest.mark.parametrize("contents", [b'\x00\x04\x00\x85',
                                      b'\x00\x05\x00\x01\x80',
                                      b'\x00\x06\x00\x81\x82\x83'])
def test_plt_dangling_continuation_byte(contents):
    properties, tests = validate(b'\xff\x58', contents)
    assert tests["ipltIsValid"] is False
    assert properties["lplt"] == len(contents)


def test_plt_length_beyond_segment():
    # Lplt claims more bytes than are present: parse what is there
    properties, tests = validate(b'\xff\x58', b'\x00\x40\x00\x05\x06')
    assert properties["iplt"] == "05,06"
    assert tests["ipltIsValid"] is True


def test_plm_dangling_continuation_byte():
    properties, tests = validate(b'\xff\x57', b'\x00\x05\x00\x01\x81')
    assert tests["iplmIsValid"] is False


def test_codestream_with_dangling_plt_in_tile_part():
    """End to end: a PLT with a dangling byte in the first tile-part header."""
    data = open(BALLOON, "rb").read()
    codestream = bytearray(data[data.find(b'jp2c') + 4:])
    sot = codestream.find(b'\xff\x90')
    psot, = struct.unpack(">I", codestream[sot + 6:sot + 10])
    plt = b'\xff\x58\x00\x04\x00\x85'
    codestream[sot + 6:sot + 10] = struct.pack(">I", psot + len(plt))
    codestream[sot + 12:sot + 12] = plt

    result = CSValidator(OPTIONS, 'codestream', bytes(codestream)).validate()

    assert result.isValid is False
    assert result.tests.find("tileParts/tilePart/plt/ipltIsValid").text is False
