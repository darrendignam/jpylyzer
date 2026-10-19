#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""PRF (ISO/IEC 15444-1 A.5.3) and CPF (ISO/IEC 15444-15 A.6) marker segments."""

import struct

import pytest

from jpylyzer.csmarkers import CSMarkerValidator

PRF, CPF = b'\xff\x56', b'\xff\x59'


def validate(marker, words, validationFormat='jph'):
    options = {'validationFormat': validationFormat, 'verboseFlag': True,
               'nullxmlFlag': False, 'packetmarkersFlag': False}
    contents = struct.pack(">H", 2 + 2 * len(words)) + b"".join(
        struct.pack(">H", word) for word in words)
    result = CSMarkerValidator(options, marker, contents).validate()
    return ({e.tag: e.text for e in result.characteristics},
            {e.tag: e.text for e in result.tests})


@pytest.mark.parametrize("words,expected", [
    ([1], 4095 + 1),
    ([1, 2], 4095 + 1 + 2 * 2 ** 16),
    ([7, 0, 3], 4095 + 7 + 3 * 2 ** 32),
])
def test_prf_number(words, expected):
    properties, tests = validate(PRF, words)
    assert properties["PRFnum"] == expected
    assert tests["pprfIsValid"] is True


def test_prf_last_word_zero():
    _, tests = validate(PRF, [1, 0])
    assert tests["pprfIsValid"] is False


@pytest.mark.parametrize("words,expected", [
    ([1], -1 + 1),
    ([1, 2], -1 + 1 + 2 * 2 ** 16),
])
def test_cpf_number(words, expected):
    properties, tests = validate(CPF, words)
    assert properties["CPFnum"] == expected
    assert tests["pcpfIsValid"] is True
    assert tests["lcpfIsValid"] is True


def test_cpf_last_word_zero():
    _, tests = validate(CPF, [1, 0])
    assert tests["pcpfIsValid"] is False


def test_cpf_tests_only_for_htj2k_formats():
    _, tests = validate(CPF, [1, 0], 'jp2')
    assert tests == {}
