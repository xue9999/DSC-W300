"""Retrieve CDX for the two actual archive-navigation links in Sony catalog."""
import sys
sys.dont_write_bytecode=True
import concurrent.futures, json
from acquire import OUT, fetch
items=[(f'year-{name}-cdx.json',f'https://web.archive.org/cdx/search/cdx?url=support.d-imaging.sony.co.jp/www/cyber-shot/update/{name}.html&output=json&filter=statuscode:200&collapse=digest&limit=30') for name in ('past','2009')]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(fetch,items))
next_items=[]
for result in results:
    if 'error' not in result:
        rows=json.loads((OUT/result['name']).read_text())
        if len(rows)>1:
            row=rows[1]
            next_items.append((f"{result['name'][:-5]}-{row[1]}.html",f'https://web.archive.org/web/{row[1]}id_/{row[2]}'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results.extend(pool.map(fetch,next_items))
(OUT/'year-followup.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,indent=2))
