#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""ICC v4 multiLocalizedUnicodeType (ICC.1:2022 10.15) in desc/cprt tags."""

import struct
import time

import pytest

from jpylyzer.icc import IccValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


def mluc(strings, recordOrder=None):
    """mluc tag with one record per string; strings stored in list order."""
    header = 16 + 12 * len(strings)
    encoded = [s.encode("utf-16-be") for s in strings]
    offsets, position = [], header
    for data in encoded:
        offsets.append(position)
        position += len(data)
    records = b"".join(b"enUS" + struct.pack(">II", len(encoded[i]), offsets[i])
                       for i in (recordOrder or range(len(strings))))
    return (b"mluc" + bytes(4) + struct.pack(">II", len(strings), 12) +
            records + b"".join(encoded))


def v4_profile(descTag):
    """Minimal v4 RGB display profile with a desc tag and a wtpt tag."""
    wtpt = b"XYZ " + bytes(4) + struct.pack(">iii", 63190, 65536, 54061)
    tags = [(b"desc", descTag), (b"wtpt", wtpt)]
    offset = 128 + 4 + 12 * len(tags)
    table, data = struct.pack(">I", len(tags)), b""
    for signature, body in tags:
        body += bytes(-len(body) % 4)
        table += signature + struct.pack(">II", offset + len(data), len(body))
        data += body
    header = (struct.pack(">I", 128 + len(table) + len(data)) + b"lcms" +
              bytes([4, 0x30, 0, 0]) + b"mntrRGB XYZ " + bytes(12) + b"acspAPPL" +
              bytes(24) + struct.pack(">iii", 63190, 65536, 54061) + b"lcms" + bytes(44))
    assert len(header) == 128
    return header + table + data


def validate(profile):
    result = IccValidator(OPTIONS, "icc", profile).validate()
    warnings = [elt.text for elt in result.warnings]
    return result.characteristics.findtext("description"), warnings


@pytest.mark.parametrize("text", ["sRGB IEC61966-2.1", "Café RGB", "日本語"])
def test_first_string_is_decoded_as_utf16(text):
    assert validate(v4_profile(mluc([text]))) == (text, [])


def test_first_record_used_when_records_not_sorted_by_offset():
    # Record 0 points to the second string in the tag, record 1 to the first
    tag = mluc(["Nom français", "English name"], recordOrder=[1, 0])
    assert validate(v4_profile(tag))[0] == "English name"


def test_zero_records():
    description, warnings = validate(v4_profile(mluc([])))
    assert description == ""
    assert warnings == ["ICC multiLocalizedUnicodeType tag contains no readable string"]


@pytest.mark.timeout(10)
def test_huge_record_count_is_not_iterated():
    tag = bytearray(mluc(["sRGB"]))
    tag[8:12] = struct.pack(">I", 0xFFFFFFFF)
    start = time.monotonic()
    assert validate(v4_profile(bytes(tag)))[0] == "sRGB"
    assert time.monotonic() - start < 1


def test_string_outside_tag():
    tag = bytearray(mluc(["sRGB"]))
    tag[24:28] = struct.pack(">I", 1000)
    assert validate(v4_profile(bytes(tag)))[0] == ""


def test_truncated_tag():
    assert validate(v4_profile(b"mluc" + bytes(4)))[0] == ""


def test_truncated_tag_table():
    profile = v4_profile(mluc(["sRGB"]))
    result = IccValidator(OPTIONS, "icc", profile[:140]).validate()
    assert result.characteristics.findall("tag") == []
