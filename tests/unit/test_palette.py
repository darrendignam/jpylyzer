#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Palette box (ISO/IEC 15444-1 I.5.3.4): NE, NPC, B_i, then NE entries that
each hold one value per column (C_ji), each value in ceil(depth / 8) bytes."""

import struct
import time

import pytest

from jpylyzer.boxes import BoxValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}
PCLR = b'\x70\x63\x6c\x72'


def pclr(depths, entries):
    """Palette box contents; depths are bit depths, entries are rows of values."""
    contents = struct.pack(">HB", len(entries), len(depths))
    contents += bytes(depth - 1 for depth in depths)
    for entry in entries:
        for depth, value in zip(depths, entry):
            contents += value.to_bytes((depth + 7) // 8, "big")
    return contents


def validate(contents):
    result = BoxValidator(OPTIONS, PCLR, contents).validate()
    c = result.characteristics
    return ([e.text for e in c.findall("cP")], [e.text for e in c.findall("bDepth")],
            {e.tag: e.text for e in result.tests})


def columns(values, nE):
    """Split the reported cP values (column by column) into columns."""
    return [values[i:i + nE] for i in range(0, len(values), nE)]


def test_values_are_assigned_to_their_columns():
    entries = [(1, 2, 3), (4, 5, 6)]
    values, depths, tests = validate(pclr([8, 8, 8], entries))
    assert columns(values, 2) == [[1, 4], [2, 5], [3, 6]]
    assert depths == [8, 8, 8]
    assert tests["boxLengthIsValid"] is True


def test_columns_with_different_byte_widths():
    entries = [(1, 1000, 7), (2, 65535, 8), (255, 0, 9)]
    values, _, tests = validate(pclr([8, 16, 4], entries))
    assert columns(values, 3) == [[1, 2, 255], [1000, 65535, 0], [7, 8, 9]]
    assert tests["boxLengthIsValid"] is True


def test_truncated_table():
    values, depths, tests = validate(pclr([8, 8, 8], [(1, 2, 3), (4, 5, 6)])[:-2])
    assert tests["boxLengthIsValid"] is False
    assert values == []
    assert depths == [8, 8, 8]


def test_huge_ne_in_tiny_box_is_not_expanded():
    contents = struct.pack(">HB", 65535, 16) + bytes([7] * 16)
    start = time.monotonic()
    values, depths, tests = validate(contents)
    assert time.monotonic() - start < 1
    assert values == []
    assert len(depths) == 16
    assert tests["nEIsValid"] is False
    assert tests["boxLengthIsValid"] is False


@pytest.mark.parametrize("nE", [1, 1024])
def test_ne_limits(nE):
    values, _, tests = validate(pclr([8], [(i % 256,) for i in range(nE)]))
    assert len(values) == nE
    assert tests["nEIsValid"] is True
