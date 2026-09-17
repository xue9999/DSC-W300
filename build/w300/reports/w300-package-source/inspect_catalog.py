"""Inspect retained catalog content offline; verify successful acquisition hashes."""
import hashlib, html, json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[4]
OUT=ROOT/'build/w300/downloads/w300-package-source'
rows=[]
for receipt in ('acquisition.json','catalog-followup.json','year-followup.json'):
    for record in json.loads((OUT/receipt).read_text(encoding='utf-8')):
        if 'sha256' in record:
            data=(OUT/record['name']).read_bytes()
            assert hashlib.sha256(data).hexdigest()==record['sha256'],record['name']
            assert len(data)==record['bytes']
            rows.append(record['name'])
catalogs=[]
for name in rows:
    if not name.endswith('.html'): continue
    text=(OUT/name).read_bytes().decode('cp932',errors='replace')
    blocks=re.findall(r'<dl\b[^>]*class="update_news"[^>]*>(.*?)</dl>',text,re.S|re.I)
    catalogs.append(dict(name=name,has_w300=bool(re.search(r'DSC[- ]?W300',text,re.I)),
        update_blocks=[html.unescape(re.sub(r'<[^>]+>',' ',b)).strip() for b in blocks],
        update_links=[html.unescape(u) for b in blocks for u in re.findall(r'href="([^"]+)"',b)]))
result=dict(verified_saved_responses=rows,catalogs=catalogs,
    boundary='Public historical consumer update catalogs only. No W300 binary or Auto-Adj package acquired.')
(pathlib.Path(__file__).parent/'inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
