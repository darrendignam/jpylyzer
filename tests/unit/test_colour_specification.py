#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Colour Specification box (ISO/IEC 15444-1 I.5.3.3, ISO/IEC 15444-15 D.4):
only the first one is tested for JP2, and fixed-size methods have a length
test."""

import os
import struct

import pytest

from jpylyzer.boxes import BoxValidator
from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

COLOUR_BOX = b'\x63\x6f\x6c\x72'
SRGB = struct.pack(">BBBI", 1, 0, 0, 16)
ROMM_RGB = struct.pack(">BBBI", 1, 1, 1, 21)
ANY_ICC = struct.pack(">BBB", 3, 0, 0) + bytes(128)
WARNING = "Colour Specification box after the first one is ignored by JP2 readers and was not tested"


def box(boxType, payload):
    return struct.pack(">I", 8 + len(payload)) + boxType + payload


def balloon_with_colour_boxes(*payloads):
    """balloon.jp2 with its colr box replaced by one colr box per payload."""
    data = open(BALLOON, "rb").read()
    start = data.find(b"colr") - 4
    length, = struct.unpack(">I", data[start:start + 4])
    colourBoxes = b"".join(box(COLOUR_BOX, payload) for payload in payloads)
    data = data[:start] + colourBoxes + data[start + length:]
    jp2h = data.find(b"jp2h") - 4
    jp2hLength, = struct.unpack(">I", data[jp2h:jp2h + 4])
    return (data[:jp2h] + struct.pack(">I", jp2hLength + len(colourBoxes) - length) +
            data[jp2h + 4:])


def check(tmp_path, *payloads):
    path = tmp_path / "colr.jp2"
    path.write_bytes(balloon_with_colour_boxes(*payloads))
    result = checkOneFile(str(path), verboseFlag=True)
    assert result.findtext("statusInfo/success") == "True"
    return result


@pytest.mark.parametrize("second", [ANY_ICC, ROMM_RGB], ids=["any_icc", "romm_rgb"])
def test_later_colour_box_is_not_tested(tmp_path, second):
    result = check(tmp_path, SRGB, second)
    assert result.findtext("isValid") == "True"
    assert len(result.findall("properties/jp2HeaderBox/colourSpecificationBox")) == 2
    assert len(result.findall("tests/jp2HeaderBox/colourSpecificationBox")) == 1
    assert WARNING in [elt.text for elt in result.iter("warning")]


def test_first_colour_box_is_tested(tmp_path):
    result = check(tmp_path, ROMM_RGB, SRGB)
    assert result.findtext("isValid") == "False"
    failed = [elt.tag for elt in result.find("tests/jp2HeaderBox/colourSpecificationBox")
              if elt.text == "False"]
    assert failed == ["precIsValid", "approxIsValid", "enumCSIsValid"]


def test_single_colour_box_has_no_warning(tmp_path):
    result = check(tmp_path, SRGB)
    assert result.findtext("isValid") == "True"
    assert WARNING not in [elt.text for elt in result.iter("warning")]


def colour_box_tests(payload, validationFormat):
    options = {'validationFormat': validationFormat, 'verboseFlag': True,
               'nullxmlFlag': False, 'packetmarkersFlag': False}
    return {elt.tag: elt.text for elt in
            BoxValidator(options, COLOUR_BOX, payload).validate().tests}


PARAMETERIZED = struct.pack(">BBBHHHB", 5, 0, 0, 1, 13, 0, 0x80)


@pytest.mark.parametrize("payload,validationFormat,expected", [
    (SRGB, "jp2", True),
    (SRGB + b"\x00", "jp2", False),
    (SRGB[:6], "jp2", False),
    (PARAMETERIZED, "jph", True),
    (PARAMETERIZED + bytes(7), "jph", False),
    (PARAMETERIZED[:9], "jph", False),
])
def test_box_length(payload, validationFormat, expected):
    assert colour_box_tests(payload, validationFormat)["boxLengthIsValid"] is expected
