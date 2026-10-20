#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""XML from xml and XMP uuid boxes is only embedded in the report if its
namespace names are URI references, which libxml2-based consumers require."""

import os
import struct

import pytest
from lxml import etree

from jpylyzer import etpatch as ET
from jpylyzer.jpylyzer import checkOneFile, NS_STRING_2

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

# balloon.jp2 has a single 'xml ' box at this offset
XML_BOX_OFFSET = 177
XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")


def balloon_with(tmp_path, xml, inUuidBox=False):
    data = open(BALLOON, "rb").read()
    length, = struct.unpack(">I", data[XML_BOX_OFFSET:XML_BOX_OFFSET + 4])
    assert data[XML_BOX_OFFSET + 4:XML_BOX_OFFSET + 8] == b"xml "
    if inUuidBox:
        box = struct.pack(">I", 24 + len(xml)) + b"uuid" + XMP_UUID + xml
    else:
        box = struct.pack(">I", 8 + len(xml)) + b"xml " + xml
    path = tmp_path / "namespaces.jp2"
    path.write_bytes(data[:XML_BOX_OFFSET] + box + data[XML_BOX_OFFSET + length:])
    return str(path)


def report(result):
    """Parse a report of this result with libxml2, as consumers do."""
    body = ET.tostring(result, "unicode", "xml")
    return etree.fromstring(('<jpylyzer xmlns="' + NS_STRING_2 + '">' + body +
                             '</jpylyzer>').encode("utf-8"))


def embedded(result, inUuidBox):
    box = result.find("properties/" + ("uuidBox" if inUuidBox else "xmlBox"))
    return box is not None and len(box) > 0


@pytest.mark.parametrize("inUuidBox", [False, True])
@pytest.mark.parametrize("uri", ["http://ns.adobe.com/photoshop/1.0/", "urn:example:a",
                                 "http://example.org/a%20b", "adobe:ns:meta/",
                                 "http://[::1]/ns", "http://[2001:db8::7]:8080/a"])
def test_valid_namespace_is_embedded(tmp_path, uri, inUuidBox):
    xml = f'<x:root xmlns:x="{uri}"><x:a>1</x:a></x:root>'.encode()
    result = checkOneFile(balloon_with(tmp_path, xml, inUuidBox))
    assert embedded(result, inUuidBox)
    report(result)


@pytest.mark.parametrize("inUuidBox", [False, True])
@pytest.mark.parametrize("xml", [
    '<x:root xmlns:x="http://^s.adobe.com/photoshop/1.0/"/>',
    '<root xmlns="not a uri"/>',
    '<root xmlns:x="http://example.org/%zz" x:attribute="1"/>',
    '<root xmlns:x="http://example.org/café"><x:a/></root>',
    '<root xmlns="http://example.org/[a]"/>',
])
def test_invalid_namespace_is_not_embedded(tmp_path, xml, inUuidBox):
    result = checkOneFile(balloon_with(tmp_path, xml.encode("utf-8"), inUuidBox))
    assert result.findtext("statusInfo/success") == "True"
    assert not embedded(result, inUuidBox)
    assert any("is not a valid URI" in warning.text for warning in result.iter("warning"))
    report(result)
