"""Print selected properties and test results from jpylyzer verbose XML output."""
import re
import sys

CHECKS = {
    'cdef_truncated_cassoc.jp2': ['cAssoc', 'cAssocIsValid', 'boxLengthIsValid'],
    'coc_component_index_5_with_csiz_3.jp2': ['csiz', 'ccoc', 'ccocIsValid'],
    'coc_components_0_and_2.jp2': ['ccoc', 'ccocValuesConsecutive', 'maxOneCcocPerComponentMain'],
    'cpf_last_word_zero.jp2': ['lcpf', 'CPFnum', 'pcpfIsValid'],
    'icc_flags_and_attributes_set.jp2': ['embeddedProfile', 'profileCannotBeUsedIndependently',
                                         'transparency', 'glossiness', 'polarity', 'colour'],
    'icc_mluc_non_ascii.jp2': ['description'],
    'icc_mluc_records_not_sorted_by_offset.jp2': ['description'],
    'ihdr_bpc_depth_65.jp2': ['bPCDepth', 'bPCIsValid'],
    'pclr_2_entries_3_columns.jp2': ['nE', 'nPC', 'bDepth', 'cP'],
    'plm_two_tileparts.jp2': ['lplm', 'nplm', 'iplm'],
    'prf_two_words.jp2': ['lprf', 'PRFnum', 'pprfIsValid'],
    'rsiz_c000_without_cap.jp2': ['rsiz', 'capability', 'rsizIsValid', 'foundCAPMarker'],
    'tlm_st_3.jp2': ['st', 'tlmStIsValid', 'ltlmIsValid', 'tpCount'],
    'xosiz_1000_yosiz_0.j2c': ['xsiz', 'ysiz', 'xOsiz', 'yOsiz', 'compressionRatio'],
    'pclr_huge_ne_tiny_box.jp2': ['nE', 'nEIsValid'],
}

outDir = sys.argv[1]
for name, tags in CHECKS.items():
    text = open(f'{outDir}/{name}.xml', encoding='utf-8').read()
    print(f'== {name}')
    for tag in tags:
        values = re.findall(rf'<{tag}>([^<]*)</{tag}>', text)
        shown = values if len(values) <= 12 else values[:12] + [f'... ({len(values)} total)']
        print(f'   {tag}: {shown if values else "(absent)"}')
    print('   failed tests:', sorted(set(re.findall(r'<(\w+)>False</\1>', text)) - {'isValid', 'success'}))
