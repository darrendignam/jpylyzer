#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""End-to-end regression tests: balloon.jp2 with one targeted edit for each
defect found in the 2.3.0rc1 review (issues #1-#25 on the review fork).

Each file must be processed without an internal error, give the expected
validity, report the expected property or test, and produce a report that
conforms to the schema.
"""

import struct

import pytest

from jpylyzer.jpylyzer import checkOneFile

from . import support

XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")

# Every case must finish well within this; several used to hang
pytestmark = pytest.mark.timeout(30)


def boxes():
    return support.parseBoxes(support.balloonBytes())


def jp2h(parsedBoxes):
    return support.findBox(parsedBoxes, b'jp2h')[1]


def withSiz(rsiz=None, **fields):
    parsed = boxes()
    layout = {'xsiz': 2, 'ysiz': 6, 'xOsiz': 10, 'yOsiz': 14, 'xTOsiz': 26, 'yTOsiz': 30}

    def edit(main, tileParts):
        siz = support.mainHeaderSegment(main, b'\xff\x51')
        parameters = bytearray(siz[1])
        if rsiz is not None:
            parameters[0:2] = struct.pack(">H", rsiz)
        for name, value in fields.items():
            parameters[layout[name]:layout[name] + 4] = struct.pack(">I", value)
        siz[1] = bytes(parameters)
    support.editCodestream(parsed, edit)
    return parsed


def withMainHeaderSegments(*segments):
    parsed = boxes()

    def edit(main, tileParts):
        cod = main.index(support.mainHeaderSegment(main, b'\xff\x52'))
        main[cod + 1:cod + 1] = [list(segment) for segment in segments]
    support.editCodestream(parsed, edit)
    return parsed


def withTilePartSegment(marker, parameters):
    parsed = boxes()
    support.editCodestream(parsed, lambda main, tileParts:
                           tileParts[0]['segments'].append([marker, parameters]))
    return parsed


def codSPcod():
    main, _, _ = support.parseCodestream(support.findBox(boxes(), b'jp2c')[1])
    return support.mainHeaderSegment(main, b'\xff\x52')[1][5:]


def coc(component):
    return (b'\xff\x53', bytes([component, 1]) + codSPcod())


def mluc(strings, recordOrder=None):
    header = 16 + 12 * len(strings)
    encoded = [s.encode("utf-16-be") for s in strings]
    offsets, position = [], header
    for data in encoded:
        offsets.append(position)
        position += len(data)
    records = b"".join(b"enUS" + struct.pack(">II", len(encoded[i]), offsets[i])
                       for i in (recordOrder or range(len(strings))))
    return (b"mluc" + bytes(4) + struct.pack(">II", len(strings), 12) + records +
            b"".join(encoded))


def iccProfile(descTag, flags=0, attributes=0):
    wtpt = b"XYZ " + bytes(4) + struct.pack(">iii", 63190, 65536, 54061)
    tags = [(b"desc", descTag), (b"wtpt", wtpt)]
    offset = 128 + 4 + 12 * len(tags)
    table, data = struct.pack(">I", len(tags)), b""
    for signature, body in tags:
        body += bytes(-len(body) % 4)
        table += signature + struct.pack(">II", offset + len(data), len(body))
        data += body
    header = (struct.pack(">I", 128 + len(table) + len(data)) + b"lcms" +
              bytes([4, 0x30, 0, 0]) + b"mntrRGB XYZ " + bytes(12) + b"acspAPPL" +
              struct.pack(">I", flags) + bytes(8) + struct.pack(">Q", attributes) + bytes(4) +
              struct.pack(">iii", 63190, 65536, 54061) + b"lcms" + bytes(44))
    return header + table + data


def withIcc(profile):
    parsed = boxes()
    support.findBox(jp2h(parsed), b'colr')[1] = bytes([2, 0, 0]) + profile
    return parsed


def withHeaderBox(boxType, payload):
    parsed = boxes()
    jp2h(parsed).append([boxType, payload])
    return parsed


def withIhdrBpc(bpc):
    parsed = boxes()
    ihdr = support.findBox(jp2h(parsed), b'ihdr')
    ihdr[1] = ihdr[1][:10] + bytes([bpc]) + ihdr[1][11:]
    return parsed


def withShortUuidBox():
    parsed = boxes()
    parsed.insert(-1, [b'uuid', bytes(8)])
    return parsed


def withUlstCount(count):
    parsed = boxes()
    ulst = support.findBox(support.findBox(parsed, b'uinf')[1], b'ulst')
    ulst[1] = struct.pack(">H", count) + ulst[1][2:]
    return parsed


def withXmpInUuidBoxOnly():
    parsed = boxes()
    xmp = support.findBox(parsed, b'xml ')[1]
    parsed = [box for box in parsed if box[0] != b'xml ']
    parsed.insert(-1, [b'uuid', XMP_UUID + xmp])
    return parsed


def texts(result, tag):
    return [elt.text for elt in result.iter(tag)]


# name: (build, format, isValid, check(result), checkOneFile keyword arguments)
CASES = {
    "plt_dangling_continuation_byte": (
        lambda: withTilePartSegment(b'\xff\x58', b'\x00\x85'), 'jp2', "False",
        lambda r: texts(r, "ipltIsValid") == ["False"], {}),
    "rsiz_0800_4k_imf_reversible": (
        lambda: withSiz(rsiz=0x0800), 'jp2', "True",
        lambda r: texts(r, "capability")[0].startswith("4k IMF Single/Multi Tile Reversible"), {}),
    "rsiz_0008_undefined_mainlevel": (
        lambda: withSiz(rsiz=0x0008), 'jp2', "True",
        lambda r: texts(r, "capability")[0].startswith("Unknown"), {}),
    "rsiz_c000_without_cap": (
        lambda: withSiz(rsiz=0xC000), 'jph', "False",
        lambda r: texts(r, "foundCAPMarker") == ["False"], {}),
    "icc_mluc_zero_records": (
        lambda: withIcc(iccProfile(mluc([]))), 'jp2', "True",
        lambda r: "ICC multiLocalizedUnicodeType tag contains no readable string"
        in texts(r, "warning"), {}),
    "icc_mluc_huge_record_count": (
        lambda: withIcc(iccProfile(mluc(["sRGB"])[:8] + struct.pack(">I", 0xFFFFFFFF) +
                                   mluc(["sRGB"])[12:])), 'jp2', "True",
        lambda r: texts(r, "description") == ["sRGB"], {}),
    "icc_mluc_non_ascii": (
        lambda: withIcc(iccProfile(mluc(["Café RGB"]))), 'jp2', "True",
        lambda r: texts(r, "description") == ["Café RGB"], {}),
    "icc_mluc_records_not_sorted_by_offset": (
        lambda: withIcc(iccProfile(mluc(["Nom français", "English name"], [1, 0]))),
        'jp2', "True", lambda r: texts(r, "description") == ["English name"], {}),
    "icc_flags_and_attributes_set": (
        lambda: withIcc(iccProfile(mluc(["Flags"]), flags=3, attributes=0xF)), 'jp2', "True",
        lambda r: texts(r, "embeddedProfile") == ["yes"] and
        texts(r, "transparency") == ["Transparent"], {}),
    "resc_zero_denominator": (
        lambda: withHeaderBox(b'res ', [[b'resc', struct.pack(">HHHHbb", 300, 0, 300, 1, 0, 0)]]),
        'jp2', "False", lambda r: texts(r, "vRescInPixelsPerMeter") == ["-9999"], {}),
    "resd_zero_denominator": (
        lambda: withHeaderBox(b'res ', [[b'resd', struct.pack(">HHHHbb", 300, 0, 300, 1, 0, 0)]]),
        'jp2', "False", lambda r: texts(r, "vResdInPixelsPerMeter") == ["-9999"], {}),
    "uuid_box_shorter_than_16_bytes": (
        withShortUuidBox, 'jp2', "False", lambda r: True, {}),
    "ulst_nu_exceeds_box": (
        lambda: withUlstCount(3), 'jp2', "False", lambda r: len(texts(r, "uuid")) == 2, {}),
    "coc_components_0_and_2": (
        lambda: withMainHeaderSegments(coc(0), coc(2)), 'jp2', "True",
        lambda r: texts(r, "ccoc") == ["0", "2"], {}),
    "coc_component_index_5_with_csiz_3": (
        lambda: withMainHeaderSegments(coc(5)), 'jp2', "False",
        lambda r: texts(r, "ccocIsValid") == ["False"], {}),
    "ihdr_bpc_depth_65": (
        lambda: withIhdrBpc(0x40), 'jp2', "False",
        lambda r: "False" in texts(r, "bPCIsValid"), {}),
    "cdef_truncated_cassoc": (
        lambda: withHeaderBox(b'cdef', struct.pack(">HHH", 1, 0, 0)), 'jp2', "False",
        lambda r: texts(r, "cAssocIsValid") == ["False"], {}),
    "prf_two_words": (
        lambda: withMainHeaderSegments((b'\xff\x56', struct.pack(">HH", 1, 2))), 'jp2', "True",
        lambda r: texts(r, "PRFnum") == ["135168"], {}),
    "cpf_last_word_zero": (
        lambda: withMainHeaderSegments((b'\xff\x59', struct.pack(">HH", 1, 0))), 'jph', "False",
        lambda r: texts(r, "pcpfIsValid") == ["False"], {}),
    "plm_two_tileparts": (
        lambda: withMainHeaderSegments((b'\xff\x57', bytes([0, 1, 0x05, 1, 0x06]))), 'jp2',
        "True", lambda r: texts(r, "iplm") == ["05", "06"], {"packetmarkersFlag": True}),
    "tlm_st_3": (
        lambda: withMainHeaderSegments((b'\xff\x55', bytes([0, 0x30]) + bytes(4))), 'jp2',
        "False", lambda r: texts(r, "tlmStIsValid") == ["False"], {}),
    "pclr_2_entries_3_columns": (
        lambda: withHeaderBox(b'pclr', struct.pack(">HB", 2, 3) + bytes([7, 7, 7, 1, 2, 3, 4, 5, 6])),
        'jp2', "False", lambda r: texts(r, "cP") == ["1", "4", "2", "5", "3", "6"], {}),
    "pclr_huge_ne_tiny_box": (
        lambda: withHeaderBox(b'pclr', struct.pack(">HB", 65535, 16) + bytes([7] * 16)),
        'jp2', "False", lambda r: texts(r, "cP") == [], {}),
    "xmp_in_uuid_box_only": (
        withXmpInUuidBoxOnly, 'jp2', "True",
        lambda r: texts(r, "mix:dateTimeCreated") == ["2008-07-19T16:14:14-07:00"],
        {"mixFlag": 2}),
}


@pytest.mark.parametrize("name", CASES)
def test_regression(tmp_path, name):
    build, validationFormat, isValid, check, options = CASES[name]
    path = tmp_path / (name + ".jp2")
    path.write_bytes(support.buildBoxes(build()))

    result = checkOneFile(str(path), validationFormat, True, **options)

    assert result.findtext("statusInfo/success") == "True", \
        result.findtext("statusInfo/failureMessage")
    assert result.findtext("isValid") == isValid
    assert check(result)
    assert support.schemaErrors([result]) == []


def test_j2c_compression_ratio_uses_y_offset(tmp_path):
    xsiz = struct.unpack(">I", support.balloonBytes()[support.balloonBytes().find(b'\xff\x51') +
                                                       6:][:4])[0]
    parsed = withSiz(xsiz=xsiz + 1000, xOsiz=1000, xTOsiz=1000)
    codestream = support.findBox(parsed, b'jp2c')[1]
    path = tmp_path / "xosiz_1000_yosiz_0.j2c"
    path.write_bytes(codestream)

    result = checkOneFile(str(path), 'j2c')

    assert result.findtext("properties/compressionRatio") == \
        str(round(3 * xsiz * 3701 / len(codestream), 2))
    assert support.schemaErrors([result]) == []
