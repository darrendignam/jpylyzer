"""Exercise the fallback in checkOneFile for modification times that
datetime.fromtimestamp rejects (ValueError on some platforms, OSError on Windows)."""
import os
import sys

sys.path.insert(0, sys.argv[1])
from jpylyzer import jpylyzer  # noqa: E402

for error in (ValueError('year is out of range'), OSError(22, 'Invalid argument')):
    def getmtime(path, error=error):
        raise error
    os.path.getmtime = getmtime
    try:
        jpylyzer.checkOneFile(sys.argv[2])
        print(type(error).__name__, '-> handled')
    except Exception as ex:
        print(type(error).__name__, '->', type(ex).__name__ + ':', ex)
