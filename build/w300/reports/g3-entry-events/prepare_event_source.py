"""Extract only G3 GPL event queue source/header as data from the pinned archive."""
from pathlib import Path
import hashlib,json,tarfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
path=ROOT/'build/w300/downloads/g3-gpl-reference/linux-kernel.tar.gz'
expected='cbb03d206740f0bcc8ed9efc90e1f48786f427188954616ed618a3cb7597e90a'
assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
members=['linux/drivers/usb/gcore/usb_event.c','linux/drivers/usb/gcore/usb_event_pvt.h','linux/include/linux/usb/gcore/usb_event.h']
out=HERE/'g3-gpl-event';out.mkdir(exist_ok=True)
records=[]
with tarfile.open(path,'r:gz') as archive:
 for name in members:
  m=archive.getmember(name);assert m.isfile();data=archive.extractfile(m).read()
  (out/Path(name).name).write_bytes(data)
  records.append({'member':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(HERE/'gpl-event-source.json').write_text(json.dumps({'archive_sha256':expected,'members':records},indent=2)+'\n')
print(json.dumps(records))
