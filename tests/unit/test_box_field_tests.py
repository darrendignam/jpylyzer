#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Box field tests that used to pass for every input (ISO/IEC 15444-1 I.5.2,
I.5.3.1, I.5.3.5, I.5.3.6)."""

import struct

import pytest

from jpylyzer.boxes import BoxValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

FTYP, IHDR, CMAP, CDEF = b'ftyp', b'ihdr', b'cmap', b'cdef'


def resultsOfTests(boxType, contents):
    result = BoxValidator(OPTIONS, boxType, contents).validate()
    return {elt.tag: elt.text for elt in result.tests}


def ihdr(bpc):
    # height, width, nC, BPC, C (7), UnkC, IPR
    return struct.pack(">IIHBBBB", 100, 100, 3, bpc, 7, 0, 0)


@pytest.mark.parametrize("bpc,expected", [
    (0x00, True),     # depth 1
    (0x07, True),     # depth 8
    (0x25, True),     # depth 38
    (0x85, True),     # signed, depth 6
    (0xFF, True),     # depth varies: see bits per component box
    (0x26, False),    # depth 39
    (0x40, False),    # depth 65
    (0x7F, False),    # depth 128
])
def test_image_header_bpc(bpc, expected):
    assert resultsOfTests(IHDR, ihdr(bpc))["bPCIsValid"] is expected


def test_channel_definition_tests_cassoc():
    # One channel description cut after Typ: Asoc is missing
    result = resultsOfTests(CDEF, struct.pack(">HHH", 1, 0, 0))
    assert result["boxLengthIsValid"] is False
    assert result["cAssocIsValid"] is False


@pytest.mark.parametrize("contents,expected", [
    (b"jp2 " + bytes(4) + b"jp2 ", True),
    (b"jp2 " + bytes(4) + b"jp2 jpx ", True),
    (b"jp2 " + bytes(4), False),        # no compatibility list
    (b"jp2 ", False),                   # no minor version
    (b"", False),
    (b"jp2 " + bytes(4) + b"jp2", False),
])
def test_file_type_box_length(contents, expected):
    assert resultsOfTests(FTYP, contents)["boxLengthIsValid"] is expected


@pytest.mark.parametrize("cmp,expected", [(0, True), (16383, True), (16384, False)])
def test_component_mapping_index(cmp, expected):
    assert resultsOfTests(CMAP, struct.pack(">HBB", cmp, 0, 0))["cMPIsValid"] is expected


@pytest.mark.parametrize("length,expected", [(4, True), (8, True), (6, False), (0, False)])
def test_component_mapping_box_length(length, expected):
    assert resultsOfTests(CMAP, bytes(length))["boxLengthIsValid"] is expected
