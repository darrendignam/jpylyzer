#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Reports for files with an empty or truncated ftyp, bpcc, pclr, cmap or cdef
box, or an empty POC marker segment, still conform to the schema."""

import os
import struct

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


def box(boxType, payload):
    return struct.pack(">I", 8 + len(payload)) + boxType + payload


def replace_box(data, boxType, edit):
    """data with the first top-level box of boxType replaced by edit(payload)."""
    offset = 0
    while True:
        length, = struct.unpack(">I", data[offset:offset + 4])
        length = length or len(data) - offset
        if data[offset + 4:offset + 8] == boxType:
            payload = data[offset + 8:offset + length]
            return data[:offset] + box(boxType, edit(payload)) + data[offset + length:]
        offset += length


def ftyp_without_cl(data):
    return replace_box(data, b"ftyp", lambda payload: payload[:8])


def jp2h_with(child):
    return lambda data: replace_box(data, b"jp2h", lambda payload: payload + child)


def empty_poc(data):
    def insert_after_cod(codestream):
        cod = codestream.find(b"\xff\x52")
        length, = struct.unpack(">H", codestream[cod + 2:cod + 4])
        end = cod + 2 + length
        return codestream[:end] + b"\xff\x5f\x00\x02" + codestream[end:]
    return replace_box(data, b"jp2c", insert_after_cod)


# name: (edit, test that reports the problem, or None when nothing does yet)
CASES = {
    "ftyp_without_cl": (ftyp_without_cl, "compatibilityListIsValid"),
    "bpcc_empty": (jp2h_with(box(b"bpcc", b"")), None),
    "pclr_npc_0": (jp2h_with(box(b"pclr", struct.pack(">HB", 1, 0))), "nPCIsValid"),
    "cmap_empty": (jp2h_with(box(b"cmap", b"")), "paletteAndComponentMappingBoxesOnlyTogether"),
    "cdef_n_0": (jp2h_with(box(b"cdef", struct.pack(">H", 0))), "nIsValid"),
    "poc_empty": (empty_poc, "lpocIsValid"),
}


@pytest.mark.parametrize("name", CASES)
def test_report_conforms_to_schema(tmp_path, name):
    edit, failingTest = CASES[name]
    path = tmp_path / (name + ".jp2")
    path.write_bytes(edit(open(BALLOON, "rb").read()))

    result = checkOneFile(str(path))

    assert result.findtext("statusInfo/success") == "True"
    if failingTest:
        assert result.findtext("isValid") == "False"
        assert "False" in [elt.text for elt in result.iter(failingTest)]
    assert schema_errors(result) == []
