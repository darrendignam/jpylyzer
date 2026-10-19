#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Validator.validate dispatch, and TLM parsing that once relied on
int.is_integer (Python 3.12+), which the dispatch error handling hid."""

import struct

import pytest

from jpylyzer import etpatch as ET
from jpylyzer.csmarkers import CSMarkerValidator
from jpylyzer.validator import Validator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


class BrokenValidator(Validator):
    def __init__(self, boxType):
        Validator.__init__(self, OPTIONS, boxType, b"")
        self.boxType = boxType
        self.tests = ET.Element("tests")

    def validate_broken(self):
        raise AttributeError("bug inside a validator")


def test_errors_inside_a_validator_are_not_hidden():
    with pytest.raises(AttributeError, match="bug inside a validator"):
        BrokenValidator("broken").validate()


def test_missing_validator_function_is_a_warning(capsys):
    BrokenValidator("missing").validate()
    assert "ignoring 'missing' (validator function not yet implemented)" in \
        capsys.readouterr().err


def tlm(stlm, entries):
    body = bytes([0, stlm]) + entries
    contents = struct.pack(">H", len(body) + 2) + body
    result = CSMarkerValidator(OPTIONS, b'\xff\x55', contents).validate()
    return ({e.tag: e.text for e in result.tests},
            result.characteristics.findtext("tpCount"),
            [e.text for e in result.characteristics.findall("ptlm")])


@pytest.mark.parametrize("stlm,entries,count,ptlms", [
    (0x00, struct.pack(">HH", 100, 200), 2, [100, 200]),            # ST 0, SP 0
    (0x50, struct.pack(">BIBI", 0, 100, 1, 200), 2, [100, 200]),    # ST 1, SP 1
    (0x20, struct.pack(">HH", 0, 100), 1, [100]),                    # ST 2, SP 0
])
def test_tlm_entries(stlm, entries, count, ptlms):
    tests, tpCount, ptlm = tlm(stlm, entries)
    assert (tests["ltlmIsValid"], tpCount, ptlm) == (True, count, ptlms)


def test_tlm_length_not_a_whole_number_of_entries():
    tests, _, _ = tlm(0x00, b"\x00\x01\x02")
    assert tests["ltlmIsValid"] is False


def test_tlm_reserved_st_value():
    tests, tpCount, _ = tlm(0x30, bytes(4))
    assert tests["tlmStIsValid"] is False
    assert tpCount == 0
