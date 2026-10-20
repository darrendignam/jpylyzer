#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Consistency between the boxes of the JP2 header: components, palette
columns, channels and colours (ISO/IEC 15444-1 I.5.3.1 to I.5.3.6), and the
IPR flag against the Intellectual Property box."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

NEW_TESTS = ["bitsPerComponentBoxOnlyIfBPCIs255", "bPCValuesConsistentWithNC",
             "cMPValuesConsistentWithNC", "pColValuesConsistentWithNPC",
             "cNValuesConsistentWithChannels", "cNValuesUnique",
             "colourChannelsConsistentWithColourSpace",
             "numberOfChannelsConsistentWithColourSpace",
             "noIntellectualPropertyBoxIfIPRIsZero"]


def box(boxType, payload):
    return struct.pack(">I", 8 + len(payload)) + boxType + payload


def cdef(*channels):
    return box(b"cdef", struct.pack(">H", len(channels)) +
               b"".join(struct.pack(">HHH", *channel) for channel in channels))


def pclr(columns):
    """Palette with 2 entries and the given number of 8-bit columns."""
    return box(b"pclr", struct.pack(">HB", 2, columns) + bytes([7] * columns) +
               bytes(2 * columns))


def cmap(*entries):
    return box(b"cmap", b"".join(struct.pack(">HBB", *entry) for entry in entries))


def balloon(headerBoxes=b"", bpc=None, ipr=None, topLevelBoxes=b""):
    """balloon.jp2 (3 components, sRGB) with extra JP2 header boxes, ihdr BPC
    and IPR values, and extra top-level boxes before the codestream."""
    data = open(BALLOON, "rb").read()
    ihdr = data.find(b"ihdr") + 4
    if bpc is not None:
        data = data[:ihdr + 10] + bytes([bpc]) + data[ihdr + 11:]
    if ipr is not None:
        data = data[:ihdr + 13] + bytes([ipr]) + data[ihdr + 14:]
    jp2h = data.find(b"jp2h") - 4
    length, = struct.unpack(">I", data[jp2h:jp2h + 4])
    data = (data[:jp2h] + struct.pack(">I", length + len(headerBoxes)) +
            data[jp2h + 4:jp2h + length] + headerBoxes + data[jp2h + length:])
    jp2c = data.find(b"jp2c") - 4
    return data[:jp2c] + topLevelBoxes + data[jp2c:]


def failed_new_tests(tmp_path, data):
    path = tmp_path / "header.jp2"
    path.write_bytes(data)
    result = checkOneFile(str(path), verboseFlag=True)
    assert result.findtext("statusInfo/success") == "True"
    return sorted({elt.tag for elt in result.iter() if elt.tag in NEW_TESTS and
                   elt.text == "False"})


# Parameters are the extra JP2 header boxes (and ihdr fields), not whole files:
# test ids built from 670 kB files exceed the 32767-character limit of the
# PYTEST_CURRENT_TEST environment variable on Windows
@pytest.mark.parametrize("headerBoxes,expected", [
    (b"", []),
    (cdef((0, 0, 1), (1, 0, 2), (2, 0, 3)), []),
    (cdef((2, 0, 3), (0, 0, 1), (1, 0, 2)), []),
    (cdef((0, 0, 1), (0, 0, 2), (2, 0, 3)), ["cNValuesUnique"]),
    (cdef((0, 0, 1), (1, 0, 2), (3, 0, 3)), ["cNValuesConsistentWithChannels"]),
    (cdef((0, 0, 1), (1, 0, 2), (2, 0, 5)), ["colourChannelsConsistentWithColourSpace"]),
    (cdef((0, 0, 1), (1, 0, 1), (2, 0, 3)), ["colourChannelsConsistentWithColourSpace"]),
    (cdef((0, 0, 1), (1, 0, 2), (2, 0, 0)), ["colourChannelsConsistentWithColourSpace"]),
    (cdef((0, 0, 1), (1, 0, 2)), ["colourChannelsConsistentWithColourSpace"]),
])
def test_channel_definitions(tmp_path, headerBoxes, expected):
    assert failed_new_tests(tmp_path, balloon(headerBoxes)) == expected


@pytest.mark.parametrize("headerBoxes,expected", [
    (pclr(3) + cmap((0, 1, 0), (0, 1, 1), (0, 1, 2)), []),
    (pclr(3) + cmap((0, 1, 0), (0, 1, 1), (0, 1, 3)), ["pColValuesConsistentWithNPC"]),
    (pclr(3) + cmap((0, 1, 0), (0, 1, 1), (3, 1, 2)), ["cMPValuesConsistentWithNC"]),
    (pclr(2) + cmap((0, 1, 0), (0, 1, 1)), ["numberOfChannelsConsistentWithColourSpace"]),
])
def test_palette_and_component_mapping(tmp_path, headerBoxes, expected):
    assert failed_new_tests(tmp_path, balloon(headerBoxes)) == expected


@pytest.mark.parametrize("headerBoxes,bpc,expected", [
    (box(b"bpcc", bytes([7, 7, 7])), 255, []),
    (box(b"bpcc", bytes([7, 7, 7])), None, ["bitsPerComponentBoxOnlyIfBPCIs255"]),
    (box(b"bpcc", bytes([7, 7])), 255, ["bPCValuesConsistentWithNC"]),
])
def test_bits_per_component(tmp_path, headerBoxes, bpc, expected):
    assert failed_new_tests(tmp_path, balloon(headerBoxes, bpc=bpc)) == expected


@pytest.mark.parametrize("ipr,expected", [
    (0, ["noIntellectualPropertyBoxIfIPRIsZero"]),
    (1, []),
])
def test_ipr_flag_with_intellectual_property_box(tmp_path, ipr, expected):
    data = balloon(ipr=ipr, topLevelBoxes=box(b"jp2i", b"<rights/>"))
    assert failed_new_tests(tmp_path, data) == expected
