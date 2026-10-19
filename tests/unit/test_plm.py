#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""PLM marker segment (ISO/IEC 15444-1 A.7.2): Lplm, Zplm, then one
(Nplm, Iplm...) group per tile-part."""

import os
import struct

import pytest
from lxml import etree

from jpylyzer import etpatch as ET
from jpylyzer.csmarkers import CSMarkerValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
XSD = os.path.join(SCRIPT_DIR, "..", "..", "xsd", "jpylyzer-v-2-3.xsd")
NAMESPACE = "http://openpreservation.org/ns/jpylyzer/v2/"

# Unterminated packet lengths once made parsing loop forever
pytestmark = pytest.mark.timeout(10)

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': True}


def plm(groups, zplm=0):
    body = bytes([zplm]) + b"".join(bytes([len(group)]) + group for group in groups)
    return struct.pack(">H", len(body) + 2) + body


def validate(contents):
    result = CSMarkerValidator(OPTIONS, b'\xff\x57', contents).validate()
    c = result.characteristics
    tests = [(e.tag, e.text) for e in result.tests]
    return ([e.text for e in c.findall("nplm")], [e.text for e in c.findall("iplm")],
            tests, c)


def test_one_group_per_tile_part():
    nplm, iplm, tests, _ = validate(plm([b"\x05", b"\x06\x81\x02"]))
    assert nplm == [1, 3]
    assert iplm == ["05", "06,0082"]
    assert all(result is True for _, result in tests)


def test_empty_group():
    nplm, iplm, _, _ = validate(plm([b"", b"\x07"]))
    assert nplm == [0, 1]
    assert iplm == ["", "07"]


def test_nplm_beyond_segment():
    # Zplm = 0, Nplm = 9, but only one Iplm byte follows
    nplm, iplm, tests, _ = validate(struct.pack(">H", 5) + bytes([0, 9, 5]))
    assert nplm == [9]
    assert iplm == ["05"]
    assert ("nplmIsValid", False) in tests


def test_dangling_continuation_byte_in_group():
    _, _, tests, _ = validate(plm([b"\x05", b"\x81"]))
    assert ("iplmIsValid", False) in tests


def test_output_conforms_to_schema():
    _, _, _, characteristics = validate(plm([b"\x05", b"\x06", b"\x07\x08"]))
    characteristics.makeHumanReadable()
    characteristics.set("xmlns", NAMESPACE)
    document = etree.fromstring(ET.tostring(characteristics, "unicode", "xml"))
    schema = etree.XMLSchema(etree.parse(XSD))
    assert schema.validate(document), schema.error_log
