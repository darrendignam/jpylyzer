#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""checkOneFile turns every per-file problem into a result for that file."""

import os
import shutil
import sys
from xml.dom import minidom

import pytest

from jpylyzer import etpatch as ET
from jpylyzer import jpylyzer
from jpylyzer.jp2 import JP2Validator

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
BALLOON = os.path.join(SCRIPT_DIR, "..", "..", "example_files", "balloon.jp2")


def as_xml(result):
    """Serialize and re-parse the way jpylyzer's pretty printer does."""
    return minidom.parseString(ET.tostring(result, "unicode", "xml"))


@pytest.mark.skipif(sys.platform == "win32", reason="control characters in file names")
def test_control_characters_in_file_name(tmp_path):
    path = tmp_path / "ctl\x01name\x1f.jp2"
    shutil.copy(BALLOON, path)
    result = jpylyzer.checkOneFile(str(path))
    as_xml(result)
    assert result.findtext("fileInfo/fileName") == "ctl\\x01name\\x1f.jp2"
    assert result.findtext("isValid") == "True"


@pytest.mark.parametrize("error", [ValueError("year is out of range"),
                                   OverflowError("timestamp out of range"),
                                   OSError(22, "Invalid argument")])
def test_unrepresentable_modification_time(monkeypatch, error):
    def getmtime(path):
        raise error
    monkeypatch.setattr(jpylyzer.os.path, "getmtime", getmtime)
    result = jpylyzer.checkOneFile(BALLOON)
    assert result.findtext("fileInfo/fileLastModified") == "1970-01-01T00:00:00"
    assert result.findtext("statusInfo/success") == "True"


def test_file_size_unavailable(monkeypatch):
    def getsize(path):
        raise FileNotFoundError(2, "No such file or directory")
    monkeypatch.setattr(jpylyzer.os.path, "getsize", getsize)
    result = jpylyzer.checkOneFile(BALLOON)
    assert result.findtext("fileInfo/fileSizeInBytes") == "-9999"


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="needs POSIX permissions and a non-root user")
def test_unreadable_file_is_an_io_error(tmp_path):
    path = tmp_path / "unreadable.jp2"
    shutil.copy(BALLOON, path)
    path.chmod(0)
    try:
        result = jpylyzer.checkOneFile(str(path))
    finally:
        path.chmod(0o600)
    assert result.findtext("statusInfo/success") == "False"
    assert result.findtext("statusInfo/failureMessage") == \
        "I/O error (cannot open file: Permission denied)"


@pytest.mark.skipif(jpylyzer.NO_MMAP_LIB, reason="memory map not used")
def test_memory_map_closed_when_validation_fails(monkeypatch):
    opened = []
    fileToMemoryMap = jpylyzer.fileToMemoryMap

    def recordingFileToMemoryMap(filename):
        fileData, warnings = fileToMemoryMap(filename)
        opened.append(fileData)
        return fileData, warnings

    def fail(self):
        raise KeyError("validator bug")

    monkeypatch.setattr(jpylyzer, "fileToMemoryMap", recordingFileToMemoryMap)
    monkeypatch.setattr(JP2Validator, "validate", fail)
    result = jpylyzer.checkOneFile(BALLOON)

    assert opened[0].closed
    assert result.findtext("statusInfo/failureMessage").startswith(
        "unknown error (KeyError: 'validator bug')")


def test_unsupported_validation_format():
    result = jpylyzer.checkOneFile(BALLOON, "jpx")
    assert result.findtext("statusInfo/success") == "False"
    assert "unsupported validation format 'jpx'" in result.findtext("statusInfo/failureMessage")
