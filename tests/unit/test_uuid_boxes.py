#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""UUID box and UUID list box (ISO/IEC 15444-1 I.7.2, I.7.3.1)."""

import os
import struct
import uuid

import pytest
from lxml import etree

from jpylyzer import etpatch as ET
from jpylyzer.boxes import BoxValidator
from jpylyzer.jpylyzer import checkOneFile, NS_STRING_2

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

UUID_BOX = b'\x75\x75\x69\x64'
UUID_LIST_BOX = b'\x75\x6c\x73\x74'
ID = uuid.UUID("12345678-1234-5678-1234-567812345678")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")
XSD = os.path.join(SCRIPT_DIR, "..", "..", "xsd", "jpylyzer-v-2-3.xsd")


def validate(boxType, contents):
    result = BoxValidator(OPTIONS, boxType, contents).validate()
    return ([elt.text for elt in result.characteristics.findall("uuid")],
            {elt.tag: elt.text for elt in result.tests})


def test_uuid_box():
    uuids, tests = validate(UUID_BOX, ID.bytes + b"data")
    assert uuids == [str(ID)]
    assert tests["boxLengthIsValid"] is True


@pytest.mark.parametrize("length", [0, 1, 8, 15])
def test_uuid_box_shorter_than_uuid(length):
    uuids, tests = validate(UUID_BOX, ID.bytes[:length])
    assert uuids == []
    assert tests["boxLengthIsValid"] is False


def test_uuid_list_box():
    uuids, tests = validate(UUID_LIST_BOX, struct.pack(">H", 2) + ID.bytes * 2)
    assert uuids == [str(ID)] * 2
    assert tests["boxLengthIsValid"] is True


@pytest.mark.parametrize("contents,expectedCount", [
    (struct.pack(">H", 3) + ID.bytes, 1),           # NU larger than the list
    (struct.pack(">H", 1) + ID.bytes[:10], 0),      # truncated UUID
    (b"\x00", 0),                                   # truncated NU
])
def test_uuid_list_box_shorter_than_nu(contents, expectedCount):
    uuids, tests = validate(UUID_LIST_BOX, contents)
    assert len(uuids) == expectedCount
    assert tests["boxLengthIsValid"] is False


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


def test_report_for_empty_uuid_list_conforms_to_schema(tmp_path):
    # balloon.jp2 with its ulst box cut to the NU field
    data = open(BALLOON, "rb").read()
    ulst = data.find(UUID_LIST_BOX) - 4
    uinf = data.find(b"uinf") - 4
    length, = struct.unpack(">I", data[ulst:ulst + 4])
    data = bytearray(data[:ulst] + struct.pack(">I", 10) + UUID_LIST_BOX +
                     data[ulst + 8:ulst + 10] + data[ulst + length:])
    uinfLength, = struct.unpack(">I", data[uinf:uinf + 4])
    data[uinf:uinf + 4] = struct.pack(">I", uinfLength - (length - 10))
    path = tmp_path / "ulst.jp2"
    path.write_bytes(bytes(data))

    result = checkOneFile(str(path))

    assert result.findtext("statusInfo/success") == "True"
    assert result.findtext("isValid") == "False"
    assert schema_errors(result) == []
