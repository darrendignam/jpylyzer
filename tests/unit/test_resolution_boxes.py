#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Capture/display resolution boxes (ISO/IEC 15444-1 I.5.3.7.1, I.5.3.7.2)."""

import struct

import pytest

from jpylyzer.boxes import BoxValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

BOX_TYPES = {"c": b'\x72\x65\x73\x63', "d": b'\x72\x65\x73\x64'}


def validate(kind, contents):
    result = BoxValidator(OPTIONS, BOX_TYPES[kind], contents).validate()
    properties = {elt.tag: elt.text for elt in result.characteristics}
    tests = {elt.tag: elt.text for elt in result.tests}
    return properties, tests


@pytest.mark.parametrize("kind", ["c", "d"])
def test_resolution_in_pixels(kind):
    # 300/1 * 10^0 vertical, 600/2 * 10^1 horizontal
    properties, tests = validate(kind, struct.pack(">HHHHbb", 300, 1, 600, 2, 0, 1))
    assert properties[f"vRes{kind}InPixelsPerMeter"] == 300
    assert properties[f"hRes{kind}InPixelsPerMeter"] == 3000
    assert properties[f"vRes{kind}InPixelsPerInch"] == 7.62
    assert properties[f"hRes{kind}InPixelsPerInch"] == 76.2
    assert all(result is True for result in tests.values())


@pytest.mark.parametrize("kind", ["c", "d"])
def test_zero_denominators(kind):
    properties, tests = validate(kind, struct.pack(">HHHHbb", 300, 0, 300, 0, 0, 0))
    assert tests[f"vR{kind}DIsValid"] is False
    assert tests[f"hR{kind}DIsValid"] is False
    assert properties[f"vRes{kind}InPixelsPerMeter"] == -9999
    assert properties[f"hRes{kind}InPixelsPerInch"] == -9999


@pytest.mark.parametrize("kind", ["c", "d"])
def test_zero_denominator_on_one_axis(kind):
    properties, _ = validate(kind, struct.pack(">HHHHbb", 300, 1, 300, 0, 0, 0))
    assert properties[f"vRes{kind}InPixelsPerMeter"] == 300
    assert properties[f"hRes{kind}InPixelsPerMeter"] == -9999


@pytest.mark.parametrize("kind", ["c", "d"])
def test_truncated_box(kind):
    # Only the vertical numerator and denominator are present
    properties, tests = validate(kind, struct.pack(">HH", 300, 1))
    assert tests["boxLengthIsValid"] is False
    assert properties[f"vRes{kind}InPixelsPerMeter"] == -9999
    assert properties[f"hRes{kind}InPixelsPerMeter"] == -9999
