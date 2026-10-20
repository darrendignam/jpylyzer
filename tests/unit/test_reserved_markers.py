#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Markers 0xFF30-0xFF3F have no marker segment parameters (ISO/IEC 15444-1
Table A.1) and are skipped, in the main header and in tile-part headers."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")


def codestream():
    data = open(BALLOON, "rb").read()
    return data[data.find(b"jp2c") + 4:]


def in_main_header(stream, marker):
    sot = stream.find(b"\xff\x90")
    return stream[:sot] + marker + stream[sot:]


def in_first_tile_part_header(stream, marker):
    sot = stream.find(b"\xff\x90")
    psot, = struct.unpack(">I", stream[sot + 6:sot + 10])
    return (stream[:sot + 6] + struct.pack(">I", psot + len(marker)) +
            stream[sot + 10:sot + 12] + marker + stream[sot + 12:])


@pytest.mark.parametrize("marker", [b"\xff\x30", b"\xff\x3f"])
@pytest.mark.parametrize("insert", [in_main_header, in_first_tile_part_header])
def test_reserved_marker_is_skipped(tmp_path, insert, marker):
    path = tmp_path / "reserved.j2c"
    path.write_bytes(insert(codestream(), marker))

    result = checkOneFile(str(path), "j2c")

    assert result.findtext("statusInfo/success") == "True"
    tests = {elt.tag: elt.text for elt in result.find("tests").iter()}
    assert "False" not in tests.values()
    assert result.findtext("isValid") == "True"
    assert len(list(result.iter("tilePart"))) == len(list(checkOneFile(BALLOON).iter("tilePart")))


def test_marker_with_parameters_after_reserved_marker(tmp_path):
    # A COM segment following FF30 is still parsed
    com = b"\xff\x64" + struct.pack(">HH", 8, 1) + b"test"
    path = tmp_path / "reserved_then_com.j2c"
    path.write_bytes(in_main_header(codestream(), b"\xff\x30" + com))

    result = checkOneFile(str(path), "j2c")

    assert result.findtext("isValid") == "True"
    assert "test" in [elt.text for elt in result.iter("comment")]


def test_empty_file_as_codestream(tmp_path):
    path = tmp_path / "empty.j2c"
    path.write_bytes(b"")

    result = checkOneFile(str(path), "j2c")

    assert result.findtext("statusInfo/success") == "True"
    assert result.findtext("isValid") == "False"
