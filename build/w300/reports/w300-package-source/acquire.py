"""Bounded public GET acquisition; no firmware execution or camera access."""
import concurrent.futures, hashlib, json, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = ROOT / 'build/w300/downloads/w300-package-source'
URLS = {
 'sony-notices.html': 'https://www.sony.jp/support/cyber-shot/whatsnew/past.html',
 'sony-relocation.html': 'https://www.sony.jp/cyber-shot/info2/20101130.html',
 'sony-w300-support.html': 'https://www.sony.jp/support/cyber-shot/products/dsc-w300/',
 'sony-update-cdx.json': 'https://web.archive.org/cdx/search/cdx?url=support.d-imaging.sony.co.jp/www/cyber-shot/update/index.html&output=json&filter=statuscode:200&collapse=digest&limit=50',
}
def fetch(item):
    name, url = item
    row = dict(name=name, url=url)
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=25) as response:
            data = response.read(4_000_001)
            if len(data)>4_000_000: raise ValueError('Response exceeds bounded HTML/index size')
            row.update(status=response.status, final_url=response.url, content_type=response.headers.get('Content-Type'))
        (OUT/name).write_bytes(data)
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        row['error'] = str(exc)
    return row
if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(fetch, URLS.items()))
    (OUT/'acquisition.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=False,indent=2))
