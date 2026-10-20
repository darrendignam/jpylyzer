#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""A CAP marker segment is required when Rsiz bit 14 is set, with or without
bit 15 (Part 2 extensions) (ISO/IEC 15444-1 Table A.10, A.5.2)."""

import os
import struct

import pytest

from jpylyzer.codestream import CSValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'jhc', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


def balloon_codestream(rsiz):
    data = open(BALLOON, "rb").read()
    codestream = bytearray(data[data.find(b'jp2c') + 4:])
    siz = codestream.find(b'\xff\x51')
    codestream[siz + 4:siz + 6] = struct.pack(">H", rsiz)
    return bytes(codestream)


@pytest.mark.parametrize("rsiz,expected", [
    (0x0000, None),     # no CAP signalled
    (0x8000, None),     # Part 2 only
    (0x4000, False),    # CAP signalled, balloon has no CAP marker
    (0xC000, False),    # Part 2 + CAP
])
def test_cap_marker_required_when_signalled(rsiz, expected):
    result = CSValidator(OPTIONS, 'codestream', balloon_codestream(rsiz)).validate()
    found = result.tests.find("foundCAPMarker")
    assert (None if found is None else found.text) is expected
