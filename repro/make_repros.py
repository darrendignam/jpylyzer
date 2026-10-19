#! /usr/bin/env python3
"""Synthesize the repro files for the jpylyzer issues.

Usage: python3 make_repros.py <balloon.jp2> <output dir> [oht-ht.jph]

Every file is balloon.jp2 (from jpylyzer's example_files) with one targeted
edit, so each one isolates a single defect. Box lengths and Psot values are
recomputed by j2k.py, so the only anomaly in each file is the one under test.
"""
import os
import struct
import sys

import j2k

XMP_UUID = bytes.fromhex('be7acfcb97a942e89c71999491e3afac')


def load(path):
    return j2k.parse_boxes(open(path, 'rb').read())


def write(boxes, outDir, name):
    path = os.path.join(outDir, name)
    with open(path, 'wb') as f:
        f.write(j2k.build_boxes(boxes))
    print('wrote', name)


def jp2h(boxes):
    return j2k.find_box(boxes, b'jp2h')[1]


def edit_siz(boxes, **fields):
    """Rewrite named SIZ fields (rsiz, xsiz, ysiz, xOsiz, yOsiz, xTOsiz, yTOsiz)."""
    layout = {'rsiz': (0, '>H'), 'xsiz': (2, '>I'), 'ysiz': (6, '>I'),
              'xOsiz': (10, '>I'), 'yOsiz': (14, '>I'), 'xTsiz': (18, '>I'),
              'yTsiz': (22, '>I'), 'xTOsiz': (26, '>I'), 'yTOsiz': (30, '>I')}

    def edit(main, tileParts):
        siz = next(segment for segment in main if segment[0] == b'\xff\x51')
        payload = bytearray(siz[1])
        for name, value in fields.items():
            offset, fmt = layout[name]
            payload[offset:offset + struct.calcsize(fmt)] = struct.pack(fmt, value)
        siz[1] = bytes(payload)
    j2k.replace_codestream(boxes, edit)


def add_main_segments(boxes, segments, after=b'\xff\x52'):
    def edit(main, tileParts):
        index = next(i for i, segment in enumerate(main) if segment[0] == after)
        main[index + 1:index + 1] = segments
    j2k.replace_codestream(boxes, edit)


def add_tilepart_segment(boxes, marker, payload):
    def edit(main, tileParts):
        tileParts[0]['segments'].append([marker, payload])
    j2k.replace_codestream(boxes, edit)


def cod_spcod(boxes):
    """SPcod of balloon's COD, reused as SPcoc so added COC segments are legal."""
    main, _, _ = j2k.parse_codestream(j2k.find_box(boxes, b'jp2c')[1])
    cod = next(segment for segment in main if segment[0] == b'\xff\x52')[1]
    return cod[5:]


def coc(component, spcod):
    # Scoc bit 0 = 1: precinct sizes follow, as in balloon's COD
    return [b'\xff\x53', bytes([component, 0x01]) + spcod]


def mluc(strings, recordOrder=None):
    """ICC multiLocalizedUnicodeType (ICC.1:2022 10.15) holding UTF-16BE strings."""
    count = len(strings)
    header = 16 + 12 * count
    encoded = [s.encode('utf-16-be') for s in strings]
    offsets, position = [], header
    for data in encoded:
        offsets.append(position)
        position += len(data)
    order = recordOrder or list(range(count))
    records = b''.join(b'enUS' + struct.pack('>II', len(encoded[i]), offsets[i])
                       for i in order)
    return b'mluc' + bytes(4) + struct.pack('>II', count, 12) + records + b''.join(encoded)


def icc_profile(descTag, flags=0, attributes=0):
    """Minimal v4 RGB display profile with a desc tag and a wtpt tag."""
    wtpt = b'XYZ ' + bytes(4) + struct.pack('>iii', 63190, 65536, 54061)
    tags = [(b'desc', descTag), (b'wtpt', wtpt)]
    tableSize = 4 + 12 * len(tags)
    offset = 128 + tableSize
    table, data = struct.pack('>I', len(tags)), b''
    for signature, body in tags:
        body += bytes(-len(body) % 4)
        table += signature + struct.pack('>II', offset + len(data), len(body))
        data += body
    size = 128 + tableSize + len(data)
    header = (struct.pack('>I', size) + b'lcms' + bytes([4, 0x30, 0, 0]) +
              b'mntr' + b'RGB ' + b'XYZ ' + struct.pack('>6H', 2026, 10, 19, 12, 0, 0) +
              b'acsp' + b'APPL' + struct.pack('>I', flags) + bytes(8) +
              struct.pack('>Q', attributes) + struct.pack('>I', 0) +
              struct.pack('>iii', 63190, 65536, 54061) + b'lcms' + bytes(16) + bytes(28))
    assert len(header) == 128
    return header + table + data


def set_colr_icc(boxes, profile):
    colr = j2k.find_box(jp2h(boxes), b'colr')
    colr[1] = bytes([2, 0, 0]) + profile


def main(balloon, outDir, jph=None):
    os.makedirs(outDir, exist_ok=True)

    # PLT whose last Iplt byte has the continuation bit set
    boxes = load(balloon)
    add_tilepart_segment(boxes, b'\xff\x58', b'\x00\x85')
    write(boxes, outDir, 'plt_dangling_continuation_byte.jp2')

    # Rsiz values from the Part 1 profile table that crash the SIZ validator
    for rsiz, name in [(0x0800, 'rsiz_0800_4k_imf_reversible.jp2'),
                       (0x0008, 'rsiz_0008_undefined_mainlevel.jp2')]:
        boxes = load(balloon)
        edit_siz(boxes, rsiz=rsiz)
        write(boxes, outDir, name)

    # Rsiz 0xC000 (Part 2 extensions + CAP) without a CAP marker segment
    boxes = load(balloon)
    edit_siz(boxes, rsiz=0xC000)
    write(boxes, outDir, 'rsiz_c000_without_cap.jp2')

    # ICC profiles
    boxes = load(balloon)
    set_colr_icc(boxes, icc_profile(mluc([])))
    write(boxes, outDir, 'icc_mluc_zero_records.jp2')

    boxes = load(balloon)
    descTag = bytearray(mluc(['sRGB']))
    descTag[8:12] = struct.pack('>I', 0xFFFFFFFF)
    set_colr_icc(boxes, icc_profile(bytes(descTag)))
    write(boxes, outDir, 'icc_mluc_huge_record_count.jp2')

    boxes = load(balloon)
    set_colr_icc(boxes, icc_profile(mluc(['Café RGB'])))
    write(boxes, outDir, 'icc_mluc_non_ascii.jp2')

    boxes = load(balloon)
    set_colr_icc(boxes, icc_profile(mluc(['English name', 'Nom français'],
                                         recordOrder=[1, 0])))
    write(boxes, outDir, 'icc_mluc_records_not_sorted_by_offset.jp2')

    boxes = load(balloon)
    set_colr_icc(boxes, icc_profile(mluc(['Flags test']), flags=0x00000003,
                                    attributes=0x000000000000000F))
    write(boxes, outDir, 'icc_flags_and_attributes_set.jp2')

    # Resolution boxes with a zero denominator
    for boxType, name in [(b'resc', 'resc_zero_denominator.jp2'),
                          (b'resd', 'resd_zero_denominator.jp2')]:
        boxes = load(balloon)
        payload = struct.pack('>HHHHbb', 300, 0, 300, 1, 0, 0)
        jp2h(boxes).append([b'res ', [[boxType, payload]]])
        write(boxes, outDir, name)

    # uuid box shorter than a UUID, and a ulst whose NU overruns the box
    boxes = load(balloon)
    boxes.insert(-1, [b'uuid', bytes(8)])
    write(boxes, outDir, 'uuid_box_shorter_than_16_bytes.jp2')

    boxes = load(balloon)
    ulst = j2k.find_box(j2k.find_box(boxes, b'uinf')[1], b'ulst')
    ulst[1] = struct.pack('>H', 3) + ulst[1][2:]
    write(boxes, outDir, 'ulst_nu_exceeds_box.jp2')

    # COC segments for components 0 and 2 only (legal), and for a component
    # index outside Csiz (illegal)
    boxes = load(balloon)
    spcod = cod_spcod(boxes)
    add_main_segments(boxes, [coc(0, spcod), coc(2, spcod)])
    write(boxes, outDir, 'coc_components_0_and_2.jp2')

    boxes = load(balloon)
    add_main_segments(boxes, [coc(5, spcod)])
    write(boxes, outDir, 'coc_component_index_5_with_csiz_3.jp2')

    # Image offset in x only, with tile grid moved along so tiling is unchanged
    boxes = load(balloon)
    main, _, _ = j2k.parse_codestream(j2k.find_box(boxes, b'jp2c')[1])
    siz = next(segment for segment in main if segment[0] == b'\xff\x51')[1]
    xsiz, = struct.unpack('>I', siz[2:6])
    edit_siz(boxes, xsiz=xsiz + 1000, xOsiz=1000, xTOsiz=1000)
    with open(os.path.join(outDir, 'xosiz_1000_yosiz_0.j2c'), 'wb') as f:
        f.write(j2k.find_box(boxes, b'jp2c')[1])
    print('wrote xosiz_1000_yosiz_0.j2c')

    # Image header with bPC depth 65 (field value 0x40); Part 1 allows 1-38
    boxes = load(balloon)
    ihdr = j2k.find_box(jp2h(boxes), b'ihdr')
    payload = bytearray(ihdr[1])
    payload[10] = 0x40
    ihdr[1] = bytes(payload)
    write(boxes, outDir, 'ihdr_bpc_depth_65.jp2')

    # Channel definition box whose single description is cut after Ctyp
    boxes = load(balloon)
    jp2h(boxes).append([b'cdef', struct.pack('>HHH', 1, 0, 0)])
    write(boxes, outDir, 'cdef_truncated_cassoc.jp2')

    # PRF with two Pprf words: 1 then 2
    boxes = load(balloon)
    add_main_segments(boxes, [[b'\xff\x56', struct.pack('>HH', 1, 2)]])
    write(boxes, outDir, 'prf_two_words.jp2')

    # CPF with two Pcpf words: 1 then 0 (last word must not be zero)
    boxes = load(balloon)
    add_main_segments(boxes, [[b'\xff\x59', struct.pack('>HH', 1, 0)]])
    write(boxes, outDir, 'cpf_last_word_zero.jp2')

    # PLM covering two tile-parts: Nplm=1, Iplm=05, then Nplm=1, Iplm=06
    boxes = load(balloon)
    add_main_segments(boxes, [[b'\xff\x57', bytes([0, 1, 0x05, 1, 0x06])]])
    write(boxes, outDir, 'plm_two_tileparts.jp2')

    # TLM with ST=3 (reserved value)
    boxes = load(balloon)
    add_main_segments(boxes, [[b'\xff\x55', bytes([0, 0x30]) + bytes(4)]])
    write(boxes, outDir, 'tlm_st_3.jp2')

    # Palette: 2 entries x 3 columns, stored entry-major as the standard says
    boxes = load(balloon)
    pclr = struct.pack('>HB', 2, 3) + bytes([7, 7, 7]) + bytes([1, 2, 3, 4, 5, 6])
    jp2h(boxes).append([b'pclr', pclr])
    write(boxes, outDir, 'pclr_2_entries_3_columns.jp2')

    # Palette: header claims 65535 entries x 16 columns, but the box is 19 bytes
    boxes = load(balloon)
    pclr = struct.pack('>HB', 65535, 16) + bytes([7] * 16)
    jp2h(boxes).append([b'pclr', pclr])
    write(boxes, outDir, 'pclr_huge_ne_tiny_box.jp2')

    # XMP stored only in a uuid box (the xml box of balloon is dropped)
    boxes = load(balloon)
    xmp = j2k.find_box(boxes, b'xml ')[1]
    boxes = [box for box in boxes if box[0] != b'xml ']
    boxes.insert(-1, [b'uuid', XMP_UUID + xmp])
    write(boxes, outDir, 'xmp_in_uuid_box_only.jp2')

    if jph:
        # Valid JPH whose colr uses method 5 (parameterized colourspace):
        # ColPrims 1 (BT.709), TransfC 13 (sRGB), MatCoeffs 0, full range
        boxes = load(jph)
        colr = j2k.find_box(jp2h(boxes), b'colr')
        colr[1] = bytes([5, 0, 0]) + struct.pack('>HHHB', 1, 13, 0, 0x80)
        write(boxes, outDir, 'colr_method_5.jph')


if __name__ == '__main__':
    # Optional third argument: oht-ht.jph from jpylyzer-test-files
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
