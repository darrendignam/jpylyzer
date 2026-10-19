#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""QCD/QCC quantization values (ISO/IEC 15444-1 A.6.4, A.6.5, Eq A-4, A-5):
one value per subband, i.e. 3 * NL + 1 for NL decomposition levels."""

import os
import struct

import pytest

from jpylyzer.csmarkers import CSMarkerValidator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")

OPTIONS = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}
QCD, QCC = b'\xff\x5c', b'\xff\x5d'


def expounded(values):
    """SPqcd words for (mu, epsilon) pairs."""
    return b"".join(struct.pack(">H", epsilon << 11 | mu) for mu, epsilon in values)


def segment(fields):
    """Marker segment contents: Lxxx followed by fields."""
    return struct.pack(">H", len(fields) + 2) + fields


def validate(marker, contents, csiz=3):
    result = CSMarkerValidator(OPTIONS, marker, contents, components=csiz).validate()
    c = result.characteristics
    return ([e.text for e in c.findall("mu")], [e.text for e in c.findall("epsilon")],
            {e.tag: e.text for e in result.tests})


def balloon_qcd():
    data = open(BALLOON, "rb").read()
    offset = data.find(QCD)
    length, = struct.unpack(">H", data[offset + 2:offset + 4])
    return data[offset + 2:offset + 2 + length]


def test_balloon_qcd_reports_every_subband():
    # Lqcd = 35, scalar expounded: NL = 5, so 16 subbands
    mu, epsilon, tests = validate(QCD, balloon_qcd())
    assert len(mu) == len(epsilon) == 16
    assert (mu[0], epsilon[0]) == (1816, 13)
    assert tests["lqcdConsistentWithQStyle"] is True


@pytest.mark.parametrize("levels", [0, 1, 5, 32])
def test_qcd_no_quantization(levels):
    values = [(e % 32) << 3 for e in range(3 * levels + 1)]
    mu, epsilon, tests = validate(QCD, segment(bytes([0x40]) + bytes(values)))
    assert mu == []
    assert epsilon == [e % 32 for e in range(3 * levels + 1)]
    assert tests["lqcdConsistentWithQStyle"] is True


@pytest.mark.parametrize("levels", [0, 1, 5])
def test_qcd_scalar_expounded(levels):
    values = [(i, i % 32) for i in range(3 * levels + 1)]
    mu, epsilon, tests = validate(QCD, segment(bytes([0x42]) + expounded(values)))
    assert list(zip(mu, epsilon)) == values
    assert tests["lqcdConsistentWithQStyle"] is True


def test_qcd_scalar_derived():
    mu, epsilon, tests = validate(QCD, segment(bytes([0x41]) + expounded([(100, 9)])))
    assert (mu, epsilon) == ([100], [9])
    assert tests["lqcdConsistentWithQStyle"] is True


@pytest.mark.parametrize("sqcd,fields", [
    (0x40, bytes(3)),                    # 3 subbands: not 3 * NL + 1
    (0x42, expounded([(1, 1)] * 2)),     # 2 subbands
    (0x42, expounded([(1, 1)]) + b"x"),  # odd number of bytes
    (0x41, expounded([(1, 1)] * 2)),     # derived with two values
])
def test_length_inconsistent_with_style(sqcd, fields):
    _, _, tests = validate(QCD, segment(bytes([sqcd]) + fields))
    assert tests["lqcdConsistentWithQStyle"] is False


@pytest.mark.parametrize("csiz,cqcc", [(3, bytes([2])), (300, struct.pack(">H", 2))])
def test_qcc_values_start_after_sqcc(csiz, cqcc):
    values = [(i + 1, i % 32) for i in range(4)]    # NL = 1
    mu, epsilon, tests = validate(QCC, segment(cqcc + bytes([0x42]) + expounded(values)), csiz)
    assert list(zip(mu, epsilon)) == values
    assert tests["lqccConsistentWithQStyle"] is True


def test_qcc_no_quantization():
    mu, epsilon, tests = validate(QCC, segment(bytes([1, 0x20]) + bytes([8, 16, 24, 32])))
    assert epsilon == [1, 2, 3, 4]
    assert tests["lqccConsistentWithQStyle"] is True
