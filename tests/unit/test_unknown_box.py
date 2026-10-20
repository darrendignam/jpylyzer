#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Unknown boxes are reported with their box type, in hexadecimal if it is
not printable ASCII."""

import pytest

from jpylyzer.boxes import BoxValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


@pytest.mark.parametrize("boxType,expected", [
    (b"rreq", "rreq"),
    (b"\xab\x97U]", "0xab97555d"),
    (b"\x00\x00\x00\x00", "0x00000000"),
    (b"jp\xc3\xa9", "0x6a70c3a9"),
])
def test_unknown_box_type(boxType, expected):
    result = BoxValidator(OPTIONS, boxType, b"").validate()
    assert result.characteristics.findtext("boxType") == expected
    assert [elt.text for elt in result.warnings] == ["ignoring unknown box '" + expected + "'"]
