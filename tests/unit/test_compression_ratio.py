#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""compressionRatio for raw codestreams uses the image area (Xsiz - XOsiz) x
(Ysiz - YOsiz) (ISO/IEC 15444-1 B.2)."""

import os
import struct

import pytest

from jpylyzer.codestream import CSValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'j2c', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}


def balloon_codestream(xOffset=0, yOffset=0):
    """balloon's codestream with the image (and tile grid) shifted by an offset,
    so the image area and tiling stay the same."""
    data = open(BALLOON, "rb").read()
    codestream = bytearray(data[data.find(b'jp2c') + 4:])
    siz = codestream.find(b'\xff\x51') + 4
    xsiz, ysiz = struct.unpack(">II", codestream[siz + 2:siz + 10])
    codestream[siz + 2:siz + 18] = struct.pack(">IIII", xsiz + xOffset, ysiz + yOffset,
                                               xOffset, yOffset)
    codestream[siz + 26:siz + 34] = struct.pack(">II", xOffset, yOffset)
    return bytes(codestream), xsiz, ysiz


@pytest.mark.parametrize("xOffset,yOffset", [(0, 0), (1000, 0), (0, 1000), (300, 700)])
def test_compression_ratio_uses_image_area(xOffset, yOffset):
    codestream, width, height = balloon_codestream(xOffset, yOffset)
    result = CSValidator(OPTIONS, 'codestream', codestream).validate()
    # balloon: 3 components of 8 bits
    expected = round(3 * width * height / len(codestream), 2)
    assert result.characteristics.findtext("compressionRatio") == expected
