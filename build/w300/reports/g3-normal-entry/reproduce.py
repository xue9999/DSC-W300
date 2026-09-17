"""Replay this bounded static G3 report only. Never load firmware or use USB."""
from pathlib import Path
import subprocess, sys
here = Path(__file__).resolve().parent
for script, args in [('inspect_entry.py', []), ('decode_entry.py', []), ('decode_entry.py', ['--extra']), ('xsb-inspect.py', []), ('verify_entry.py', [])]:
    subprocess.run([sys.executable, str(here / script), *args], check=True)
