#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""ICC profile flags (ICC.1:2022 7.2.11) and device attributes (7.2.14).

ICC numbers bits from the least significant bit: flag bit 0 is "embedded",
attribute bit 0 is "transparency" (LittleCMS: cmsEmbeddedProfileTrue = 0x1,
cmsTransparency = 1, cmsMatte = 2).
"""

import struct

import pytest

from jpylyzer import byteconv as bc
from jpylyzer.icc import IccValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

FLAG_NAMES = ["embeddedProfile", "profileCannotBeUsedIndependently"]
ATTRIBUTE_NAMES = ["transparency", "glossiness", "polarity", "colour"]


def profile_header(flags, attributes):
    """128-byte v4 profile header plus an empty tag table."""
    header = (struct.pack(">I", 132) + b"lcms" + bytes([4, 0x30, 0, 0]) +
              b"mntrRGB XYZ " + bytes(12) + b"acspAPPL" + struct.pack(">I", flags) +
              bytes(8) + struct.pack(">Q", attributes) + bytes(4) +
              struct.pack(">iii", 63190, 65536, 54061) + b"lcms" + bytes(44))
    assert len(header) == 128
    return header + struct.pack(">I", 0)


def reported(profile, names):
    characteristics = IccValidator(OPTIONS, "icc", profile).validate().characteristics
    return [characteristics.findtext(name) for name in names]


@pytest.mark.parametrize("flags,expected", [
    (0x00000000, [0, 0]),
    (0x00000001, [1, 0]),
    (0x00000002, [0, 1]),
    (0x00000003, [1, 1]),
    (0xFFFF0000, [0, 0]),    # vendor-defined bits 16-31 only
])
def test_profile_flags(flags, expected):
    assert reported(profile_header(flags, 0), FLAG_NAMES) == expected


@pytest.mark.parametrize("attributes,expected", [
    (0x0, [0, 0, 0, 0]),
    (0x1, [1, 0, 0, 0]),
    (0x2, [0, 1, 0, 0]),
    (0x4, [0, 0, 1, 0]),
    (0x8, [0, 0, 0, 1]),
    (0xF, [1, 1, 1, 1]),
    (0xFFFFFFFF00000000, [0, 0, 0, 0]),    # vendor-defined high 32 bits only
])
def test_device_attributes(attributes, expected):
    assert reported(profile_header(0, attributes), ATTRIBUTE_NAMES) == expected


def test_truncated_header():
    # Cut before the flags field (byte 44)
    assert reported(profile_header(3, 0xF)[:40], FLAG_NAMES + ATTRIBUTE_NAMES) == [-9999] * 6


def test_bit_value_from_right():
    assert [bc.getBitValueFromRight(0b1010, p) for p in range(4)] == [0, 1, 0, 1]
    assert bc.getBitValueFromRight(-9999, 0) == -9999


def warnings(profile):
    return [e.text for e in IccValidator(OPTIONS, "icc", profile).validate().warnings]


@pytest.mark.parametrize("flags,attributes,expected", [
    (0x00000003, 0xFFFFFFFF0000000F, 0),    # defined and vendor bits only
    (0x00000004, 0x0, 1),
    (0x0, 0x37FA98, 1),    # sRGB v4 profile in jpylyzer-test-files icc_v4_appearance.jp2
    (0x8000, 0x10, 2),
])
def test_reserved_bits_set(flags, attributes, expected):
    assert len([w for w in warnings(profile_header(flags, attributes))
                if "reserved bits" in w]) == expected


def test_no_reserved_bit_warning_for_truncated_header():
    assert not [w for w in warnings(profile_header(0, 0)[:40]) if "reserved bits" in w]
