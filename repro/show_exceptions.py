"""Run the JP2 validator directly on files that jpylyzer reports as 'unknown error'
and print the underlying exception (checkOneFile hides it)."""
import sys
import traceback

sys.path.insert(0, sys.argv[1])
from jpylyzer.jp2 import JP2Validator  # noqa: E402

options = {'validationFormat': 'jp2', 'verboseFlag': True,
           'nullxmlFlag': False, 'packetmarkersFlag': False}
for path in sys.argv[2:]:
    print('==', path.rsplit('/', 1)[-1])
    try:
        JP2Validator(options, 'JP2', open(path, 'rb').read()).validate()
        print('   no exception')
    except Exception:
        frame = traceback.extract_tb(sys.exc_info()[2])[-1]
        print(f'   {type(sys.exc_info()[1]).__name__}: {sys.exc_info()[1]}')
        print(f'   at {frame.filename.rsplit("/", 2)[-2]}/{frame.filename.rsplit("/", 1)[-1]}:{frame.lineno}: {frame.line}')
