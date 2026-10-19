#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""Robustness against malformed input: deterministic mutations of balloon.jp2.

Whatever the damage, jpylyzer must finish quickly, report the file without an
internal error ("unknown error"), and produce a report that conforms to the
schema. Every case is seeded, so a failure can be reproduced exactly from the
test id.
"""

import random

import pytest

from jpylyzer.jpylyzer import checkOneFile

from . import support

CASES_PER_FORMAT = 150

pytestmark = pytest.mark.timeout(10)


def codestream():
    data = support.balloonBytes()
    return data[data.find(b'jp2c') + 4:]


def mutate(data, seed):
    """One of: truncation, byte changes in the headers, a 4-byte overwrite
    anywhere, an extreme marker segment length, or an extreme box length."""
    rng = random.Random(seed)
    mutated = bytearray(data)
    kind = rng.randrange(5)
    if kind == 0:
        mutated = mutated[:rng.randrange(1, len(mutated))]
    elif kind == 1:
        for _ in range(rng.randrange(1, 8)):
            mutated[rng.randrange(min(len(mutated), 4096))] = rng.randrange(256)
    elif kind == 2:
        position = rng.randrange(len(mutated))
        mutated[position:position + 4] = bytes(rng.randrange(256) for _ in range(4))
    elif kind == 3:
        markers = [i for i in range(min(len(mutated), 8192) - 4)
                   if mutated[i] == 0xFF and mutated[i + 1] >= 0x4F]
        position = rng.choice(markers)
        mutated[position + 2:position + 4] = rng.choice(
            [b'\x00\x00', b'\x00\x01', b'\x00\x02', b'\xff\xff'])
    else:
        boxes = [i for i in range(min(len(mutated), 8192) - 8)
                 if bytes(mutated[i + 4:i + 8]).isalpha()]
        position = rng.choice(boxes)
        mutated[position:position + 4] = rng.choice(
            [b'\x00\x00\x00\x00', b'\x00\x00\x00\x01', b'\x00\x00\x00\x08', b'\xff\xff\xff\xff'])
    return bytes(mutated)


@pytest.mark.parametrize("validationFormat,seed",
                         [(f, s) for f in ("jp2", "jph", "j2c")
                          for s in range(CASES_PER_FORMAT)])
def test_mutated_file(tmp_path, validationFormat, seed):
    source = codestream() if validationFormat == "j2c" else support.balloonBytes()
    path = tmp_path / ("mutated." + validationFormat)
    path.write_bytes(mutate(source, seed))

    result = checkOneFile(str(path), validationFormat, True, packetmarkersFlag=True)

    assert result.findtext("statusInfo/success") == "True", \
        result.findtext("statusInfo/failureMessage")
    assert support.schemaErrors([result]) == []
