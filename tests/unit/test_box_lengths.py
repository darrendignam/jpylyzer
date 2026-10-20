#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Box lengths (ISO/IEC 15444-1 I.4): LBox 2-7 and XLBox below 16 are
invalid, a box must fit in its superbox or the file, and only the last box
of the file may have LBox 0."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")


def box(boxType, payload):
    return struct.pack(">I", 8 + len(payload)) + boxType + payload


def balloon():
    return open(BALLOON, "rb").read()


def set_length(data, boxType, value):
    start = data.find(boxType) - 4
    return data[:start] + value + data[start + 4:]


def with_header_box(data, child):
    jp2h = data.find(b"jp2h") - 4
    length, = struct.unpack(">I", data[jp2h:jp2h + 4])
    return (data[:jp2h] + struct.pack(">I", length + len(child)) +
            data[jp2h + 4:jp2h + length] + child + data[jp2h + length:])


def length_tests(tmp_path, data):
    path = tmp_path / "lengths.jp2"
    path.write_bytes(data)
    result = checkOneFile(str(path), verboseFlag=True)
    assert result.findtext("statusInfo/success") == "True"
    return (result.findtext("tests/boxLengthsAreValid"),
            result.findtext("tests/jp2HeaderBox/subBoxLengthsAreValid"))


def test_balloon(tmp_path):
    assert length_tests(tmp_path, balloon()) == ("True", "True")


def test_last_box_with_length_0(tmp_path):
    # balloon.jp2 ends with a contiguous codestream box with LBox 0
    data = balloon()
    assert struct.unpack(">I", data[data.find(b"jp2c") - 4:data.find(b"jp2c")]) == (0,)
    assert length_tests(tmp_path, data)[0] == "True"


def test_last_box_with_extended_length(tmp_path):
    data = balloon()
    jp2c = data.find(b"jp2c") - 4
    length = len(data) - jp2c + 8
    data = data[:jp2c] + struct.pack(">I", 1) + b"jp2c" + struct.pack(">Q", length) + \
        data[jp2c + 8:]
    assert length_tests(tmp_path, data)[0] == "True"


@pytest.mark.parametrize("value", [struct.pack(">I", 2), struct.pack(">I", 7)])
def test_reserved_box_length(tmp_path, value):
    assert length_tests(tmp_path, set_length(balloon(), b"uinf", value))[0] == "False"


def test_extended_length_below_16(tmp_path):
    data = balloon()
    uinf = data.find(b"uinf") - 4
    data = data[:uinf] + struct.pack(">I", 1) + b"uinf" + struct.pack(">Q", 9) + data[uinf + 8:]
    assert length_tests(tmp_path, data)[0] == "False"


def test_box_past_end_of_file(tmp_path):
    data = balloon()
    data = set_length(data, b"jp2c", struct.pack(">I", len(data)))
    assert length_tests(tmp_path, data)[0] == "False"


def test_trailing_bytes_shorter_than_box_header(tmp_path):
    data = set_length(balloon(), b"jp2c", struct.pack(">I", len(balloon()) -
                                                      balloon().find(b"jp2c") + 4))
    assert length_tests(tmp_path, data + b"\x00\x00\x00")[0] == "False"


def test_sub_box_past_end_of_superbox(tmp_path):
    data = balloon()
    colr = data.find(b"colr") - 4
    data = data[:colr] + struct.pack(">I", 4194319) + data[colr + 4:]
    assert length_tests(tmp_path, data)[1] == "False"


def test_sub_box_with_length_0(tmp_path):
    data = with_header_box(balloon(), struct.pack(">I", 0) + b"xml " + b"<a/>")
    assert length_tests(tmp_path, data)[1] == "False"
