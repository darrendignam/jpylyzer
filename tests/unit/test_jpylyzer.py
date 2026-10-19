#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import sys
import pytest

from jpylyzer.jpylyzer import __version__, checkNoInput, EXISTING_FILES, getFiles
import jpylyzer.config as config

def test_version():
    assert __version__

def test_empty_input_files():
    with pytest.raises(SystemExit) as pytest_wrapped_excep:
        checkNoInput([])
    assert pytest_wrapped_excep.type == SystemExit
    assert pytest_wrapped_excep.value.code == config.ERR_CODE_NO_IMAGES

def test_null_input_files():
    with pytest.raises(SystemExit) as pytest_wrapped_excep:
        checkNoInput(None)
    assert pytest_wrapped_excep.type == SystemExit
    assert pytest_wrapped_excep.value.code == config.ERR_CODE_NO_IMAGES

def test_get_files():
    assert not EXISTING_FILES
    getFiles('./*')
    assert EXISTING_FILES
    if sys.version_info > (3, 0):
        EXISTING_FILES.clear()
        assert not EXISTING_FILES
