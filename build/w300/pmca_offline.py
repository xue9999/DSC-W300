"""Launch pinned PMCA help with the local USB runtime; never accept live commands.

The original console is in upstream/Sony-PMCA-RE/pmca-console.py. Its live
commands are not qualified for W300. This bootstrap verifies import/startup
without opening a device, then the upstream program displays its own help.
"""
from pathlib import Path
import runpy
import sys
import libusb_package

if len(sys.argv) != 1:
    raise SystemExit('Offline launcher takes no arguments and sends no camera commands')
if libusb_package.get_libusb1_backend() is None:
    raise SystemExit('Local USB runtime failed to load')
source = Path(__file__).resolve().parent / 'upstream' / 'Sony-PMCA-RE'
sys.path.insert(0, str(source))
sys.argv = [str(source / 'pmca-console.py'), '--help']
runpy.run_path(sys.argv[0], run_name='__main__')
