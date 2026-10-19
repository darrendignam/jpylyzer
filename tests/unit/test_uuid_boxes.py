#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""UUID box and UUID list box (ISO/IEC 15444-1 I.7.2, I.7.3.1)."""

import struct
import uuid

import pytest

from jpylyzer.boxes import BoxValidator

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}

UUID_BOX = b'\x75\x75\x69\x64'
UUID_LIST_BOX = b'\x75\x6c\x73\x74'
ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


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
