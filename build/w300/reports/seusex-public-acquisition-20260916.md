# SeusEX public package acquisition: historical catalog route

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

Date: 2026-09-16. Bounded follow-up to `auto-adj-acquisition.md` and `ibiss-acquisition.md`, which were consulted first. Scope is SeusEX package acquisition without a camera connection; no W300 Auto-Adj broad search, portal login, forms, contact, purchases, credential use, installation, or program execution.

## Outcome

The historical download locator was recovered and tested. Its redirect and archive responses are retained below; use this coverage to pursue a new binary-bearing SeusEX source and inspect actual installer contents.

The useful new evidence is the actual 2009 Software Informer download-page HTML. It redirects to `http://43.7.166.43/?lang=en&uid=` rather than to a SeusEX ZIP/EXE. The empty `uid` is reproduced as found; no identifier or credential was supplied. The live endpoint timed out, and the public archive index has no saved software payload under that host. Thus the old catalog's download button and claimed download count must not be treated as proof that it ever hosted the binary.

## New route 1: distinguish catalog versions from actual payloads

At the time of this check, the [download page](https://seusex.software.informer.com/download/) explicitly said the link was missing. Both [1.9](https://seusex.software.informer.com/1.9/) and [1.1](https://seusex.software.informer.com/1.1/) direct to a request-for-link facility, not an installer. The [versions page](https://seusex.software.informer.com/versions/) gives catalog dates in 2009, but offers no precise package filenames or checksums. No form was submitted.

A direct PowerShell request to the current download page encountered a Cloudflare JavaScript/cookie challenge. This is an access/environment limitation, separate from the public page's explicit missing-download result, which the web browsing tool could read. No challenge workaround was attempted. The helper left a zero-byte local file, preserved under the explicit name `software-informer-live-empty-after-failed-request.txt`; it is not downloaded page content or a program.

[UpdateStar](https://seusex.updatestar.com/) also explicitly reports no download available; its catalog does not establish a package version. [PC Matic](https://www.pcmatic.com/company/libraries/software/detail.asp?id=0&title=SeusEX) supplies a program name/manufacturer entry, not a SeusEX payload link. Neither page is an authenticated Sony distribution.

The catalog supplied no software package. Acquisition must continue before runtime dependencies can be assessed.

## New route 2: retrieve historical HTML and follow the actual locator

Public Internet Archive CDX prefix queries succeeded for Software Informer. The actual index contains early versions 1.6, 1.7, 1.8 and 1.9 plus a `/download` capture. That is new evidence beyond the modern catalog's visible versions.

Three specific snapshots were fetched over normal verified HTTPS and inspected as text, without running embedded scripts:

| Saved file | Archive URL | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `catalog-snapshot-0.html` | `https://web.archive.org/web/20090828200417id_/http://seusex.software.informer.com:80/download` | 7777 | `86B386C42CAFD575E995BFF7DD897DE57C6186A959722EECD427C05FCE4BB86F` |
| `catalog-snapshot-1.html` | `https://web.archive.org/web/20090828172016id_/http://seusex.software.informer.com:80/` | 14314 | `E067F7240C763774FACD18805C635DA77E59E4A55F03475C3B86C87FADE88B9B` |
| `catalog-snapshot-2.html` | `https://web.archive.org/web/20090831070303id_/http://seusex.software.informer.com:80/wiki/` | 15200 | `152774E63AAE9EF10BA0D045D82A1A984CA789A75E44B7FF34A092B6FE8663F0` |

In the first file, lines 88-89 build `http://43.7.166.43/?lang=en&uid=` using string concatenation. This is not a downloadable package filename. The second file calls the application executable `SeusEX.exe` and lists catalog versions 1.6-1.9; these are third-party inventory statements, not binary metadata or W300 compatibility evidence. The wiki snapshot contains an unfilled entry and a `siinst.exe` advertisement for the Software Informer client. That unrelated executable was not downloaded.

The locator was followed through bounded read-only checks:

| Test | Result | Classification and action |
| --- | --- | --- |
| CDX prefix `seusex.software.informer.com/`, status 200, unique URLs | HTTP 200, 14 capture rows | Actual archived HTML inventory, no EXE/ZIP capture in returned rows; retrieved useful historical pages. |
| CDX prefix `seusex.updatestar.com/`, status 200 | HTTP 200, `[]` | No successful captures returned for this exact prefix. |
| CDX prefix `43.7.166.43/`, status 200, unique URLs, limit 1000 | HTTP 200; only one row, `robots.txt` dated 2005 | No package payload or landing-page capture returned. Limit did not truncate the single-row result. |
| Replay of that exact archived `robots.txt` | HTTP 404 | Archive index/replay inconsistency; no payload inferred. |
| Actual observed locator `http://43.7.166.43/?lang=en&uid=` | 15-second HTTP-client timeout | Live endpoint unavailable to this host; nothing downloaded. This single legacy HTTP request carried no credentials or camera data. |
| CDX exact historical download URL, unique digests | HTTP 503 | Archive endpoint failure; changed to the bounded post-2010 prefix query below. |
| CDX download-prefix query from 2010, status 200, unique digests | HTTP 200, `[]` | No later successful download-page captures returned under this prefix. |

No current ownership of the historical IP address is asserted. Do not try to log in or infer authorization from an old catalog redirect.

## New route 3: precise package and service-reference queries

Targeted queries used filename fragments and disjoint repository/domain filters to avoid repeating the already exhausted W300 Auto-Adj searches. Representative exact searches:

```text
"SeusEX_x64" -site:someatechkb.blob.core.windows.net
"SeusEX" "128200" -site:someatechkb.blob.core.windows.net
"SeusEX" (site:sony.net OR site:sony.com OR site:sony.eu OR site:sony.co.jp)
"SeusEX" (site:elektroda.pl OR site:remont-aud.net OR site:eletronicabr.com OR site:elektrotanya.com)
"SeusEX" (site:github.com OR site:archive.org OR site:mediafire.com OR site:4shared.com OR site:mega.nz OR site:drive.google.com)
"SeusEX" "1.6" "Sony"
"SeusEX" filetype:zip
```

No new exact payload URL was returned. Publicly indexed service manuals give model-specific tools and describe SeusEX as a separately installed dependency, while the already-known ASC training screenshot remains the only precise `SeusEX_x64_128200.zip` filename locator. No token from the indexed training-document URL was used, and the previously failed token-free document endpoint was not repeated. Search engines sometimes returned excluded/manual results; those were treated as irrelevant references, not as a positive archive result.

Finding and follow-up: no package locator from the examined references, not evidence that SeusEX cannot exist elsewhere. Lens-tool requirements are not generalized to W300.

## Local evidence and reproduction

All new materials are under `build/w300/downloads/seusex-public-20260916/`. `artifact-manifest.json` records actual sizes and SHA-256 hashes. `catalog-archive-results.json`, `snapshot-results.json`, `legacy-locator-results.json`, and `legacy-followup-results.json` record exact URLs, successful saves and errors. The corresponding CDX files preserve the actual returned indices.

Read-only replay of the discovery query:

```powershell
Invoke-WebRequest -Uri 'https://web.archive.org/cdx/search/cdx?url=seusex.software.informer.com/&matchType=prefix&output=json&filter=statuscode:200&collapse=urlkey' |
  Select-Object StatusCode, Content
```

For the SeusEX route, acquire actual package bytes and inspect the compatible USB driver/runtime, any legitimate HASP requirement and the W300-specific operation. Use the retained HTML as locator evidence; verify the payload before planning execution. If these public references produce no additional package link, continue the independent W300 firmware/trace and file-acquisition preparation routes in the [execution plan](../../../docs/w300/EXECUTION_PLAN.md). No executable was run, no driver was installed, and no camera communication or language change occurred in this check.
