#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""foundExpectedNumberOfTiles and foundExpectedNumberOfTileParts: tiles with
only empty tile-components may be absent (ISO/IEC 15444-1 Equations B-7 to
B-12), and tnsot 0 means "number of tile-parts not given" (A.4.2)."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

# SIZ of ISO/IEC 15444-4 conformance codestream b2_mono.j2c: 5 x 5 tiles, of
# which tiles 0-4, 9, 14, 19 and 24 have an empty tile-component
B2_MONO = dict(xsiz=1519, ysiz=697, xOsiz=1, yOsiz=160, xTsiz=379, yTsiz=161,
               xTOsiz=0, yTOsiz=0, separations=[(5, 3)])
B2_MONO_EMPTY = {0, 1, 2, 3, 4, 9, 14, 19, 24}


def segment(marker, parameters):
    return marker + struct.pack(">H", len(parameters) + 2) + parameters


def balloon_segment(marker):
    data = open(BALLOON, "rb").read()
    start = data.find(marker)
    length, = struct.unpack(">H", data[start + 2:start + 4])
    return data[start:start + 2 + length]


def tile_part(isot, tpsot=0, tnsot=1):
    # Psot covers SOT (12 bytes) and SOD (2 bytes); no packet data
    return segment(b"\xff\x90", struct.pack(">HIBB", isot, 14, tpsot, tnsot)) + b"\xff\x93"


def codestream(tileParts, xsiz, ysiz, xOsiz, yOsiz, xTsiz, yTsiz, xTOsiz, yTOsiz,
               separations):
    siz = struct.pack(">HIIIIIIIIH", 0, xsiz, ysiz, xOsiz, yOsiz, xTsiz, yTsiz,
                      xTOsiz, yTOsiz, len(separations))
    siz += b"".join(struct.pack(">BBB", 7, x, y) for x, y in separations)
    return (b"\xff\x4f" + segment(b"\xff\x51", siz) + balloon_segment(b"\xff\x52") +
            balloon_segment(b"\xff\x5c") + b"".join(tileParts) + b"\xff\xd9")


def tile_tests(tmp_path, data):
    path = tmp_path / "tiles.j2c"
    path.write_bytes(data)
    result = checkOneFile(str(path), "j2c", verboseFlag=True)
    assert result.findtext("statusInfo/success") == "True"
    return tuple(next(result.iter(test)).text for test in
                 ("foundExpectedNumberOfTiles", "foundExpectedNumberOfTileParts"))


def test_tiles_with_only_empty_tile_components_may_be_absent(tmp_path):
    tiles = [tile_part(t) for t in range(25) if t not in B2_MONO_EMPTY]
    assert tile_tests(tmp_path, codestream(tiles, **B2_MONO)) == ("True", "True")


def test_empty_tiles_may_also_be_present(tmp_path):
    tiles = [tile_part(t) for t in range(25)]
    assert tile_tests(tmp_path, codestream(tiles, **B2_MONO)) == ("True", "True")


def test_missing_tile_with_samples(tmp_path):
    tiles = [tile_part(t) for t in range(25) if t not in B2_MONO_EMPTY | {12}]
    assert tile_tests(tmp_path, codestream(tiles, **B2_MONO))[0] == "False"


def test_tile_index_outside_grid(tmp_path):
    tiles = [tile_part(t) for t in range(25)] + [tile_part(30)]
    assert tile_tests(tmp_path, codestream(tiles, **B2_MONO))[0] == "False"


GRID_2X2 = dict(xsiz=64, ysiz=64, xOsiz=0, yOsiz=0, xTsiz=32, yTsiz=32,
                xTOsiz=0, yTOsiz=0, separations=[(1, 1)])


@pytest.mark.parametrize("tileParts,expected", [
    # Like conformance codestream p0_10.j2k: tnsot 0 for some tile-parts,
    # 2 for others, and tile 2 never states its number of tile-parts
    ([(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0), (0, 1, 2), (1, 1, 2), (3, 1, 2),
      (2, 1, 0), (2, 2, 0)], "True"),
    ([(0, 0, 2), (1, 0, 1), (2, 0, 1), (3, 0, 1)], "False"),   # tile 0: 1 of 2
    ([(0, 0, 1), (0, 1, 0), (1, 0, 1), (2, 0, 1), (3, 0, 1)], "False"),  # tile 0: 2, not 1
])
def test_tile_parts_with_tnsot_0(tmp_path, tileParts, expected):
    data = codestream([tile_part(*fields) for fields in tileParts], **GRID_2X2)
    assert tile_tests(tmp_path, data) == ("True", expected)


def test_empty_image_area_requires_all_tiles(tmp_path):
    # yOsiz beyond ysiz: no tile has samples, which is a SIZ error rather
    # than a reason to accept missing tiles
    grid = dict(GRID_2X2, yOsiz=1000)
    tiles = [tile_part(t) for t in (0, 1, 3)]
    assert tile_tests(tmp_path, codestream(tiles, **grid))[0] == "False"
