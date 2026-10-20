#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""COC/QCC component overrides (ISO/IEC 15444-1 A.6.2, A.6.5).

The standard allows at most one COC/QCC per component in a header, for any
subset of the components and in any order.
"""

import os
import struct

import pytest

from jpylyzer.codestream import CSValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'j2c', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

COD, QCD = b'\xff\x52', b'\xff\x5c'


def balloon_codestream():
    data = open(BALLOON, "rb").read()
    return data[data.find(b'jp2c') + 4:]


def segment_contents(codestream, marker):
    """Marker segment parameters after the length field."""
    offset = codestream.find(marker)
    length, = struct.unpack(">H", codestream[offset + 2:offset + 4])
    return codestream[offset + 4:offset + 2 + length]


def with_main_header_segments(codestream, segments):
    """Insert segments into the main header, just before the first SOT."""
    sot = codestream.find(b'\xff\x90')
    return codestream[:sot] + b"".join(segments) + codestream[sot:]


def segment(marker, contents):
    return marker + struct.pack(">H", len(contents) + 2) + contents


def coc(codestream, component):
    # Scoc = 1 (precinct sizes follow), SPcoc copied from COD (balloon has Csiz=3)
    spcod = segment_contents(codestream, COD)[5:]
    return segment(b'\xff\x53', bytes([component, 1]) + spcod)


def qcc(codestream, component):
    # Sqcc and SPqcc copied from QCD
    return segment(b'\xff\x5d', bytes([component]) + segment_contents(codestream, QCD))


def validate(segments):
    codestream = balloon_codestream()
    built = with_main_header_segments(codestream, [make(codestream, c) for make, c in segments])
    return CSValidator(OPTIONS, 'codestream', built).validate()


@pytest.mark.parametrize("components", [[0, 2], [2, 0], [1], [2, 1, 0]])
def test_coc_for_any_subset_of_components_is_valid(components):
    result = validate([(coc, c) for c in components])
    assert result.isValid is True
    assert [e.text for e in result.characteristics.findall("coc/ccoc")] == components


@pytest.mark.parametrize("components", [[0, 2], [2, 0]])
def test_qcc_for_any_subset_of_components_is_valid(components):
    result = validate([(qcc, c) for c in components])
    assert result.isValid is True


def test_two_coc_for_the_same_component_are_invalid():
    result = validate([(coc, 1), (coc, 1)])
    assert result.isValid is False
    assert result.tests.findtext("maxOneCcocPerComponentMain") is False


def test_two_qcc_for_the_same_component_are_invalid():
    result = validate([(qcc, 0), (qcc, 0)])
    assert result.isValid is False
    assert result.tests.findtext("maxOneCqccPerComponentMain") is False
