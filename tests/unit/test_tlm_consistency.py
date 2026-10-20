#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""TLM marker segments against the tile-parts (ISO/IEC 15444-1 A.7.1): tile
indices, ztlm uniqueness and ztlm order."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")


def segment(marker, parameters):
    return marker + struct.pack(">H", len(parameters) + 2) + parameters


def balloon_segment(marker):
    data = open(BALLOON, "rb").read()
    start = data.find(marker)
    length, = struct.unpack(">H", data[start + 2:start + 4])
    return data[start:start + 2 + length]


def tile_part(isot, tpsot=0, tnsot=1):
    return segment(b"\xff\x90", struct.pack(">HIBB", isot, 14, tpsot, tnsot)) + b"\xff\x93"


def tlm(ztlm, entries, st=1):
    """TLM with sp = 1 (32-bit Ptlm); entries are tile indices (ignored for st 0)."""
    parameters = struct.pack(">BB", ztlm, (st << 4) | 0x40)
    for isot in entries:
        parameters += (struct.pack(">B", isot) if st == 1 else b"") + struct.pack(">I", 14)
    return segment(b"\xff\x55", parameters)


def codestream(tlms, isots):
    """2 x 2 tiles of 32 x 32, one component, one tile-part per isot value."""
    siz = struct.pack(">HIIIIIIIIHBBB", 0, 64, 64, 0, 0, 32, 32, 0, 0, 1, 7, 1, 1)
    return (b"\xff\x4f" + segment(b"\xff\x51", siz) + balloon_segment(b"\xff\x52") +
            balloon_segment(b"\xff\x5c") + b"".join(tlms) +
            b"".join(tile_part(isot) for isot in isots) + b"\xff\xd9")


def tlm_tests(tmp_path, data):
    path = tmp_path / "tlm.j2c"
    path.write_bytes(data)
    result = checkOneFile(str(path), "j2c", verboseFlag=True)
    assert result.findtext("statusInfo/success") == "True"
    names = ("ztlmValuesUnique", "tilePartLengthsConsistencyCheck",
             "tileIndicesTLMConsistencyCheck")
    return tuple(next(result.iter(name)).text for name in names)


@pytest.mark.parametrize("tlms,isots,expected", [
    ([tlm(0, [0, 1, 2, 3])], [0, 1, 2, 3], ("True", "True", "True")),
    ([tlm(0, [0, 1, 3, 2])], [0, 1, 2, 3], ("True", "True", "False")),
    # st = 0: tile-part i is tile i
    ([tlm(0, range(4), st=0)], [0, 1, 2, 3], ("True", "True", "True")),
    ([tlm(0, range(4), st=0)], [0, 1, 3, 2], ("True", "True", "False")),
    # Two segments, in ztlm order and reversed
    ([tlm(0, [0, 1]), tlm(1, [2, 3])], [0, 1, 2, 3], ("True", "True", "True")),
    ([tlm(1, [2, 3]), tlm(0, [0, 1])], [0, 1, 2, 3], ("True", "True", "True")),
    ([tlm(0, [0, 1]), tlm(0, [2, 3])], [0, 1, 2, 3], ("False", "True", "True")),
])
def test_tlm_against_tile_parts(tmp_path, tlms, isots, expected):
    assert tlm_tests(tmp_path, codestream(tlms, isots)) == expected
