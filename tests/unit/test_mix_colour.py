#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""MIX PhotometricInterpretation, and MIX failures that must not abort a run."""

import os
import struct

import pytest

from jpylyzer import mix
from jpylyzer.jpylyzer import checkOneFile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

# Offsets of the jp2h superbox and its ihdr and colr boxes in balloon.jp2
JP2H, IHDR, COLR, JP2H_END = 32, 40, 62, 77


def balloon_with_colr(tmp_path, colrContents, nC=None):
    """balloon.jp2 with its colour specification box replaced."""
    data = open(BALLOON, "rb").read()
    assert data[JP2H + 4:JP2H + 8] == b"jp2h" and data[COLR + 4:COLR + 8] == b"colr"
    ihdr = bytearray(data[IHDR:COLR])
    if nC is not None:
        ihdr[16:18] = struct.pack(">H", nC)
    colr = struct.pack(">I", 8 + len(colrContents)) + b"colr" + colrContents
    jp2h = bytes(ihdr) + colr
    path = tmp_path / "colr.jp2"
    path.write_bytes(data[:JP2H] + struct.pack(">I", 8 + len(jp2h)) + b"jp2h" + jp2h +
                     data[JP2H_END:])
    return str(path)


def parameterized(matCoeffs):
    """METH 5 colr: ColPrims 1, TransfC 13, given MatCoeffs, full range."""
    return bytes([5, 0, 0]) + struct.pack(">HHHB", 1, 13, matCoeffs, 0x80)


def mix_colour_space(path):
    # Validity does not matter here: generate MIX from the reported properties
    properties = checkOneFile(path).find("properties")
    # MIX elements carry a literal "mix:" prefix, so match tags, not paths
    colorSpaces = mix.Mix(2).generateMixBasicImageInformation(properties).iter("mix:colorSpace")
    return next((elt.text for elt in colorSpaces), None)


@pytest.mark.parametrize("colr,nC,expected", [
    (bytes([1, 0, 0]) + struct.pack(">I", 16), None, "sRGB"),
    (parameterized(0), None, "RGB"),
    (parameterized(1), None, "YCbCr"),
    (parameterized(0), 1, "greyscale"),
])
def test_colour_space(tmp_path, colr, nC, expected):
    assert mix_colour_space(balloon_with_colr(tmp_path, colr, nC)) == expected


def test_unknown_colour_specification_has_no_photometric_interpretation(tmp_path):
    # METH 4 (vendor colour) is not in balloon's colr, so nothing to map
    assert mix_colour_space(balloon_with_colr(tmp_path, bytes([4, 0, 0]) + bytes(20))) is None


def test_rdf_without_description():
    rdf = mix.ET.Element("rdf")
    assert mix.Mix.findValueInRDF(rdf, "Description", "{ns}", "tag") is None


def test_mix_failure_is_a_warning_not_an_abort(monkeypatch):
    def fail(self, properties):
        raise AttributeError("'NoneType' object has no attribute 'text'")
    monkeypatch.setattr(mix.Mix, "generateMix", fail)

    result = checkOneFile(BALLOON, mixFlag=2)

    assert result.findtext("statusInfo/success") == "True"
    assert list(result.iter("mix:mix")) == []
    assert any("could not generate MIX" in w.text for w in result.iter("warning"))


def test_mix_for_codestream_formats_is_not_generated():
    result = checkOneFile(BALLOON, "j2c", mixFlag=2)
    assert result.findtext("statusInfo/success") == "True"
