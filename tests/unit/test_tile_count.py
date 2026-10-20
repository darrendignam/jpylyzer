#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Tile and tile-part counting for codestreams with many tiles."""

import os
import struct

import pytest

from jpylyzer.codestream import CSValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'j2c', 'verboseFlag': False,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


def tiled_codestream(tileSize, tileIndices):
    """balloon's main header with the given tile size, followed by one empty
    tile-part (SOT + SOD) for each index in tileIndices, then EOC."""
    data = open(BALLOON, "rb").read()
    codestream = bytearray(data[data.find(b'jp2c') + 4:])
    siz = codestream.find(b'\xff\x51') + 4
    codestream[siz + 18:siz + 26] = struct.pack(">II", tileSize, tileSize)
    mainHeader = bytes(codestream[:codestream.find(b'\xff\x90')])
    tileParts = b"".join(b'\xff\x90' + struct.pack(">HHIBB", 10, index, 14, 0, 1) + b'\xff\x93'
                         for index in tileIndices)
    xsiz, ysiz = struct.unpack(">II", codestream[siz + 2:siz + 10])
    numberOfTiles = -(-xsiz // tileSize) * -(-ysiz // tileSize)
    return mainHeader + tileParts + b'\xff\xd9', numberOfTiles


def found_expected_number_of_tiles(codestream):
    result = CSValidator(OPTIONS, 'codestream', codestream).validate()
    test = result.tests.find("foundExpectedNumberOfTiles")
    return True if test is None else test.text


def test_many_tiles():
    _, numberOfTiles = tiled_codestream(32, [])
    assert numberOfTiles == 85 * 116
    codestream, _ = tiled_codestream(32, range(numberOfTiles))
    assert found_expected_number_of_tiles(codestream) is True


@pytest.mark.parametrize("dropLast,expected", [(False, True), (True, False)])
def test_repeated_tile_index_counts_once(dropLast, expected):
    """Tile 0 appears twice; with the last tile dropped one tile is missing."""
    _, numberOfTiles = tiled_codestream(1024, [])
    indices = list(range(numberOfTiles - 1 if dropLast else numberOfTiles)) + [0]
    codestream, _ = tiled_codestream(1024, indices)
    assert found_expected_number_of_tiles(codestream) is expected
