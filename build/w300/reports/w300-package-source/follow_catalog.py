"""Follow two specific successful historical catalog captures from CDX."""
import sys
sys.dont_write_bytecode=True
import concurrent.futures, json
from acquire import OUT, fetch
rows=json.loads((OUT/'sony-update-cdx.json').read_text())
items=[]
for row in (rows[1],rows[-1]):
    items.append((f'update-{row[1]}.html',f'https://web.archive.org/web/{row[1]}id_/{row[2]}'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(fetch,items))
(OUT/'catalog-followup.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,indent=2))
