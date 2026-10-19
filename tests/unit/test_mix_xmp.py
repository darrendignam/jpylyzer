#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""MIX ImageCaptureMetadata from XMP in an XML box or an XMP UUID box."""

import os
import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

# balloon.jp2 has its XMP in a single 'xml ' box at this offset
XML_BOX_OFFSET = 177
XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")


def balloon_xml_box():
    data = open(BALLOON, "rb").read()
    length, = struct.unpack(">I", data[XML_BOX_OFFSET:XML_BOX_OFFSET + 4])
    assert data[XML_BOX_OFFSET + 4:XML_BOX_OFFSET + 8] == b"xml "
    return data, length


def balloon_with_xmp_in(tmp_path, where):
    """balloon.jp2 with its XMP in the xml box, a uuid box, both, or neither."""
    data, length = balloon_xml_box()
    xmp = data[XML_BOX_OFFSET + 8:XML_BOX_OFFSET + length]
    boxes = b""
    if "xml" in where:
        boxes += data[XML_BOX_OFFSET:XML_BOX_OFFSET + length]
    if "uuid" in where:
        boxes += struct.pack(">I", 24 + len(xmp)) + b"uuid" + XMP_UUID + xmp
    path = tmp_path / "xmp.jp2"
    path.write_bytes(data[:XML_BOX_OFFSET] + boxes + data[XML_BOX_OFFSET + length:])
    return str(path)


def date_time_created(path):
    result = checkOneFile(path, mixFlag=2)
    return [elt.text for elt in result.iter("mix:dateTimeCreated")]


@pytest.mark.parametrize("where", [("xml",), ("uuid",), ("xml", "uuid")])
def test_image_capture_metadata_from_xmp(tmp_path, where):
    assert date_time_created(balloon_with_xmp_in(tmp_path, where)) == \
        ["2008-07-19T16:14:14-07:00"]


def test_no_xmp_no_image_capture_metadata(tmp_path):
    path = balloon_with_xmp_in(tmp_path, ())
    assert list(checkOneFile(path, mixFlag=2).iter("mix:ImageCaptureMetadata")) == []
