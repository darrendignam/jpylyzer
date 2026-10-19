#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Command line behaviour: exit codes, file discovery, tool name."""

import os
import shutil
import subprocess
import sys

import pytest

from jpylyzer import config, shared
from jpylyzer import jpylyzer

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
JPYLYZER_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
BALLOON = os.path.join(JPYLYZER_DIR, "example_files", "balloon.jp2")
TRUNCATED = os.path.join(JPYLYZER_DIR, "example_files", "balloon_trunc2.jp2")


def checked_file_names(capsys, recurse, paths):
    jpylyzer.checkFiles(recurse, paths)
    output = capsys.readouterr().out
    return [line.strip()[len("<fileName>"):-len("</fileName>")]
            for line in output.splitlines() if "<fileName>" in line]


def test_error_exit_status():
    with pytest.raises(SystemExit) as exitInfo:
        shared.errorExit("something is wrong")
    assert exitInfo.value.code == config.ERR_CODE_INVALID_INPUT != 0


def test_unsupported_format_exits_with_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["jpylyzer", "--format", "foo", BALLOON])
    with pytest.raises(SystemExit) as exitInfo:
        jpylyzer.main()
    assert exitInfo.value.code == config.ERR_CODE_INVALID_INPUT


def test_files_from_earlier_calls_are_not_checked_again(capsys):
    assert checked_file_names(capsys, False, [BALLOON]) == ["balloon.jp2"]
    assert checked_file_names(capsys, False, [TRUNCATED]) == ["balloon_trunc2.jp2"]


def test_overlapping_inputs_report_each_file_once(capsys, tmp_path):
    shutil.copy(BALLOON, tmp_path / "x.jp2")
    names = checked_file_names(capsys, True, [str(tmp_path / "x.jp2"), str(tmp_path)])
    assert names == ["x.jp2"]


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links")
def test_unique_files_resolves_links(tmp_path):
    shutil.copy(BALLOON, tmp_path / "a.jp2")
    (tmp_path / "b.jp2").symlink_to(tmp_path / "a.jp2")
    paths = [str(tmp_path / "a.jp2"), str(tmp_path / "b.jp2"), str(tmp_path / "a.jp2")]
    assert jpylyzer.uniqueFiles(paths) == [str(tmp_path / "a.jp2")]


def test_tool_name_when_run_as_module():
    output = subprocess.run([sys.executable, "-m", "jpylyzer", BALLOON], cwd=JPYLYZER_DIR,
                            capture_output=True, text=True, check=True).stdout
    assert "<toolName>jpylyzer</toolName>" in output
