#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
Tests on the openjpeg-data corpus (https://github.com/uclouvain/openjpeg-data):
the ISO/IEC 15444-4 conformance files in input/conformance and the malformed
and unusual files collected in input/nonregression.

The openjpeg-data root directory is either given by the JPYLYZER_OPENJPEG_DATA
environment variable, or present in a sibling directory of the jpylyzer dir
named openjpeg-data. If neither is found, all tests in this module are
skipped.
"""

import os

import pytest

from jpylyzer.jpylyzer import checkOneFile

from . import support

OPENJPEG_DATA = os.environ.get(
    "JPYLYZER_OPENJPEG_DATA",
    os.path.join(os.path.dirname(support.JPYLYZER_DIR), "openjpeg-data"))
INPUT_DIR = os.path.join(OPENJPEG_DATA, "input")

if not os.path.isdir(INPUT_DIR):
    pytest.skip("openjpeg-data not found at " + OPENJPEG_DATA +
                " (set JPYLYZER_OPENJPEG_DATA to its root directory)",
                allow_module_level=True)

SIGNATURE = b'\x00\x00\x00\x0cjP  \r\n\x87\n'

# Tests that ISO/IEC 15444-4 JP2 conformance files fail although they are
# conformance files: APPROX is 1 in all of them (ISO/IEC 15444-1 I.5.3.3 says
# it shall be 0), and file5/file7 have brand 'jpx '
CONFORMANCE_JP2_FAILURES = {name: ["approxIsValid"] for name in
                            ["file1.jp2", "file2.jp2", "file3.jp2", "file4.jp2",
                             "file6.jp2", "file8.jp2", "file9.jp2"]}
CONFORMANCE_JP2_FAILURES.update({name: ["approxIsValid", "brandIsValid"]
                                 for name in ["file5.jp2", "file7.jp2"]})


def files(subdirectory):
    root = os.path.join(INPUT_DIR, subdirectory)
    return sorted(os.path.relpath(os.path.join(directory, name), INPUT_DIR)
                  for directory, _, names in os.walk(root) for name in names)


def native_format(path):
    with open(path, "rb") as f:
        head = f.read(12)
    if head == SIGNATURE:
        return "jp2"
    if head[:2] == b"\xff\x4f":
        return "j2c"
    return None


def failed_tests(result):
    return sorted({elt.tag for elt in result.find("tests").iter() if elt.text == "False"})


@pytest.mark.timeout(60)
@pytest.mark.parametrize("name", files("conformance") + files("nonregression"))
def test_report(name):
    """Every file, JPEG 2000 or not, gives a complete report that conforms to
    the schema."""
    path = os.path.join(INPUT_DIR, name)
    validationFormat = native_format(path) or "jp2"
    options = {"packetmarkersFlag": True}
    if validationFormat == "jp2":
        options["mixFlag"] = 2

    result = checkOneFile(path, validationFormat, True, **options)

    assert result.findtext("statusInfo/success") == "True", \
        result.findtext("statusInfo/failureMessage")
    assert support.schemaErrors([result]) == []


@pytest.mark.parametrize("name", [name for name in files("conformance")
                                  if native_format(os.path.join(INPUT_DIR, name))])
def test_conformance_file(name):
    """Conformance files are valid by definition, apart from the documented
    exceptions."""
    path = os.path.join(INPUT_DIR, name)
    validationFormat = native_format(path)

    result = checkOneFile(path, validationFormat, True)

    expected = CONFORMANCE_JP2_FAILURES.get(os.path.basename(name), [])
    assert failed_tests(result) == expected
