# jpylyzer 2.3.0rc1 review: repro files

Synthesized files and scripts that reproduce the defects reported in this
fork's issue tracker. All observations were made against `2.3.0rc1`
(commit `c238c04`, identical to `origin/master` and `origin/2-3-dev` on
2026-10-19) with CPython 3.12, except where a Python version is stated.

## Files

Every JP2 in `files/` is `example_files/balloon.jp2` with one targeted edit.
`j2k.py` rebuilds box lengths and `Psot` values, so the edit under test is the
only anomaly. `colr_method_5.jph` is built the same way from `oht-ht.jph`
in [jpylyzer-test-files](https://github.com/openpreserve/jpylyzer-test-files).

| File | Edit | Shows |
|---|---|---|
| `plt_dangling_continuation_byte.jp2` | PLT `Zplt=0, Iplt=0x85` in first tile-part | infinite loop in `_parse_ipl` |
| `rsiz_0800_4k_imf_reversible.jp2` | `Rsiz=0x0800` | `UnboundLocalError` in SIZ validator |
| `rsiz_0008_undefined_mainlevel.jp2` | `Rsiz=0x0008` | `UnboundLocalError` in SIZ validator |
| `rsiz_c000_without_cap.jp2` | `Rsiz=0xC000`, no CAP | `foundCAPMarker` never tested |
| `icc_mluc_zero_records.jp2` | v4 ICC, `desc` mluc with 0 records | `IndexError` in `readmultiLocalizedUnicodeType` |
| `icc_mluc_huge_record_count.jp2` | v4 ICC, mluc record count `0xFFFFFFFF` | hang (killed after 20 s) |
| `icc_mluc_non_ascii.jp2` | mluc string `Café RGB` | empty `description` |
| `icc_mluc_records_not_sorted_by_offset.jp2` | 2 mluc records, record order not offset order | empty `description` |
| `icc_flags_and_attributes_set.jp2` | flags `0x00000003`, attributes `0x...0F` | all six flag properties reported as unset |
| `resc_zero_denominator.jp2` | `resc` with `VRcD=0` | `ZeroDivisionError` |
| `resd_zero_denominator.jp2` | `resd` with `VRdD=0` | `ZeroDivisionError` |
| `uuid_box_shorter_than_16_bytes.jp2` | `uuid` box with 8 content bytes | `ValueError` from `uuid.UUID` |
| `ulst_nu_exceeds_box.jp2` | `ulst` with `NU=3`, one UUID present | `ValueError` from `uuid.UUID` |
| `coc_components_0_and_2.jp2` | COC for components 0 and 2 (Csiz=3) | valid file reported invalid (`ccocValuesConsecutive`) |
| `coc_component_index_5_with_csiz_3.jp2` | COC with `Ccoc=5`, Csiz=3 | invalid file reported valid |
| `xosiz_1000_yosiz_0.j2c` | `XOsiz=1000`, `YOsiz=0` (tiling unchanged) | wrong `compressionRatio` |
| `ihdr_bpc_depth_65.jp2` | `ihdr` BPC `0x40` (depth 65) | `bPCIsValid` is True |
| `cdef_truncated_cassoc.jp2` | `cdef` with N=1 and no `Asoc` field | `cAssoc=-9999`, `cAssocIsValid` True |
| `prf_two_words.jp2` | PRF with `Pprf = 1, 2` | wrong `PRFnum` |
| `cpf_last_word_zero.jp2` | CPF with `Pcpf = 1, 0` | wrong `CPFnum`, `pcpfIsValid` never emitted |
| `plm_two_tileparts.jp2` | PLM `Zplm=0, (Nplm=1, 05), (Nplm=1, 06)` | `iplm = 05,01,06` |
| `tlm_st_3.jp2` | TLM with `ST=3` | TLM output dropped on Python < 3.12 |
| `pclr_2_entries_3_columns.jp2` | `pclr` NE=2, NPC=3, entries `(1,2,3), (4,5,6)` | entries assigned to the wrong columns |
| `pclr_huge_ne_tiny_box.jp2` | 19-byte `pclr` claiming NE=65535, NPC=16 | 1,048,560 `cP` elements, 32.5 MB of XML |
| `xmp_in_uuid_box_only.jp2` | balloon XMP moved from `xml ` box to XMP `uuid` box | MIX `ImageCaptureMetadata` missing |
| `colr_method_5.jph` | valid JPH, `colr` METH=5 | `--mix` aborts the whole run |

## Scripts

- `make_repros.py balloon.jp2 files/ [oht-ht.jph]`: regenerates `files/`.
- `run_all.sh <jpylyzer dir> files/ <out dir>`: runs `cli.py --verbose
  --packetmarkers` on every file with a 20 s timeout, and prints the exit code,
  run time, `success` and `isValid`.
- `inspect_output.py <out dir>`: prints the properties and tests that matter for
  each file.
- `show_exceptions.py <jpylyzer dir> files...`: shows the exception behind an
  "unknown error" (`checkOneFile` discards it).
- `mtime_fallback.py <jpylyzer dir> <file>`: exercises the modification time
  fallback in `checkOneFile`.

`observed-2.3.0rc1/` holds the output of these scripts against `2.3.0rc1`.
The output for `pclr_huge_ne_tiny_box.jp2` is truncated to its first lines.

## PR 249

`pr249/byte-range.patch` is the alternative fix proposed for
[openpreserve/jpylyzer#249](https://github.com/openpreserve/jpylyzer/pull/249).
It applies to `2.3.0rc1` with `git apply`.
