#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Marker segments in the wrong header, or repeated where only one is allowed
(ISO/IEC 15444-1 Table A.2, A.6.1, A.6.4, A.6.6, A.7.4, A.7.5)."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

TLM = b"\xff\x55" + struct.pack(">HBB", 4, 0, 0)
PLT = b"\xff\x58" + struct.pack(">HBB", 4, 0, 5)
PPT = b"\xff\x61" + struct.pack(">HBB", 4, 0, 0)
PPM = b"\xff\x60" + struct.pack(">HB", 3, 0)
POC = b"\xff\x5f" + struct.pack(">HBBHBBB", 9, 0, 0, 1, 5, 3, 0)


def codestream():
    data = open(BALLOON, "rb").read()
    return data[data.find(b"jp2c") + 4:]


def segment_at(stream, marker):
    start = stream.find(marker)
    length, = struct.unpack(">H", stream[start + 2:start + 4])
    return stream[start:start + 2 + length]


def in_main_header(stream, insert):
    sot = stream.find(b"\xff\x90")
    return stream[:sot] + insert + stream[sot:]


def in_first_tile_part_header(stream, insert):
    sot = stream.find(b"\xff\x90")
    psot, = struct.unpack(">I", stream[sot + 6:sot + 10])
    return (stream[:sot + 6] + struct.pack(">I", psot + len(insert)) +
            stream[sot + 10:sot + 12] + insert + stream[sot + 12:])


def failed_tests(tmp_path, data):
    path = tmp_path / "markers.j2c"
    path.write_bytes(data)
    result = checkOneFile(str(path), "j2c", verboseFlag=True)
    assert result.findtext("statusInfo/success") == "True"
    return sorted({elt.tag for elt in result.find("tests").iter() if elt.text == "False"})


def test_balloon_passes(tmp_path):
    assert failed_tests(tmp_path, codestream()) == []


@pytest.mark.parametrize("insert,expected", [
    (lambda s: segment_at(s, b"\xff\x52"), ["maxOneCODMain"]),
    (lambda s: segment_at(s, b"\xff\x5c"), ["maxOneQCDMain"]),
    (lambda s: POC + POC, ["maxOnePOCMain"]),
    (lambda s: PLT, ["mainHeaderMarkersAllowed"]),
    (lambda s: PPT, ["mainHeaderMarkersAllowed"]),
    (lambda s: b"\xff\x93", ["mainHeaderMarkersAllowed"]),
    (lambda s: b"\xff\xd9", ["mainHeaderMarkersAllowed"]),
])
def test_main_header(tmp_path, insert, expected):
    stream = codestream()
    assert failed_tests(tmp_path, in_main_header(stream, insert(stream))) == expected


@pytest.mark.parametrize("insert,expected", [
    (lambda s: segment_at(s, b"\xff\x52") * 2, ["maxOneCODTP"]),
    (lambda s: segment_at(s, b"\xff\x5c") * 2, ["maxOneQCDTP"]),
    (lambda s: POC + POC, ["maxOnePOCTP"]),
    (lambda s: TLM, ["tilePartHeaderMarkersAllowed"]),
    (lambda s: segment_at(s, b"\xff\x51"), ["tilePartHeaderMarkersAllowed"]),
    (lambda s: PPM, ["tilePartHeaderMarkersAllowed"]),
])
def test_tile_part_header(tmp_path, insert, expected):
    stream = codestream()
    assert failed_tests(tmp_path, in_first_tile_part_header(stream, insert(stream))) == expected


def test_single_cod_qcd_poc_in_tile_part_header(tmp_path):
    stream = codestream()
    insert = segment_at(stream, b"\xff\x52") + segment_at(stream, b"\xff\x5c") + POC
    assert failed_tests(tmp_path, in_first_tile_part_header(stream, insert)) == []


def test_ppm_and_ppt(tmp_path):
    stream = in_first_tile_part_header(in_main_header(codestream(), PPM), PPT)
    assert "noPPTMarkersWithPPM" in failed_tests(tmp_path, stream)
