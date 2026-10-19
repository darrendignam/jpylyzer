#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Reports for files whose SIZ has no readable components still conform to
the schema."""

import os

import pytest
from lxml import etree

from jpylyzer import etpatch as ET
from jpylyzer.jpylyzer import checkOneFile, NS_STRING_2

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")
XSD = os.path.join(SCRIPT_DIR, "..", "..", "xsd", "jpylyzer-v-2-3.xsd")


def schema_errors(result):
    toolInfo = ET.Element("toolInfo")
    toolInfo.appendChildTagWithText("toolName", "jpylyzer")
    toolInfo.appendChildTagWithText("toolVersion", "test")
    body = ET.tostring(toolInfo, "unicode", "xml") + ET.tostring(result, "unicode", "xml")
    report = etree.fromstring(('<jpylyzer xmlns="' + NS_STRING_2 + '">' + body +
                               '</jpylyzer>').encode("utf-8"))
    schema = etree.XMLSchema(etree.parse(XSD))
    schema.validate(report)
    return [str(error) for error in schema.error_log]


@pytest.mark.parametrize("edit", [
    "lsiz_4",      # SIZ truncated after Rsiz: csiz cannot be read
    "csiz_0",      # no components
])
def test_report_conforms_to_schema(tmp_path, edit):
    data = bytearray(open(BALLOON, "rb").read())
    siz = data.find(b'\xff\x51')
    if edit == "lsiz_4":
        data[siz + 2:siz + 4] = b"\x00\x04"
    else:
        data[siz + 38:siz + 40] = b"\x00\x00"
    path = tmp_path / "siz.jp2"
    path.write_bytes(bytes(data))

    result = checkOneFile(str(path))

    assert result.findtext("statusInfo/success") == "True"
    assert result.findtext("isValid") == "False"
    assert schema_errors(result) == []
