# IBISS locator acquisition audit

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

Date: 2026-09-16. Scope: resolve the previously partial `/IBISS_Files/DSC/Software/` reference into an actual public SeusEX or DSC-W300 Auto-Adj package. Read-only network checks, no camera connection, no portal login, no credentials/tokens, no installation or binary execution.

## Result

The route below resolved the service portal and an exact package-name lead. Continue acquisition through a new concrete binary-bearing locator, then inspect the actual archive and its W300 support. The partial forum locator has now been traced to a live Sony login portal, and the relevant public archive prefixes were checked successfully. A publicly indexed training screenshot provides a concrete x64 SeusEX archive filename, but not its payload URL or proof of W300 compatibility.

## Concrete findings

1. The raw public HTML of [the W270 Seus discussion](https://forum-monitor.net.ru/threads/585578/) contains `/IBISS_Files/DSC/Software/` only as plain text (saved HTML lines 3051 and 5027), not as an `href` with a recoverable filename. The later post explicitly calls this an incomplete link. This is a W270 discussion, not evidence that its adjustment software works with W300.
2. [A second W270 discussion](https://forum-monitor.net.ru/threads/387492/) names `www.ibiss.crse.com` and directs the participant to `ADJUST STATION`. Its public text also distinguishes the model adjustment program, a suitable SEUS version, and HASP. The www hostname currently fails DNS.
3. The canonical hostname **[https://ibiss.crse.com/](https://ibiss.crse.com/)** works: HTTP 200, 471-byte HTML, meta-refresh to **[https://ibiss.sony.eu/accounts/login?application_id=ibiss](https://ibiss.sony.eu/accounts/login?application_id=ibiss)**. The destination is a 5476-byte HTTP 200 page with User ID, Password and Log In controls. Only the public page was read; no login, password reset, form submission, or credential use was attempted.
4. The exact observed relative directory on the canonical host, `https://ibiss.crse.com/IBISS_Files/DSC/Software/`, returns **HTTP 404**. This does not prove that all formerly hosted package files are absent; it means the observed directory itself is not a public listing.
5. Sony's public [Pro-Assist description](https://pro.sony/en_GB/support-services/pro-assist) expressly says software cannot be downloaded from Pro-Assist. It describes access validation using a service contract or professional IBISS account. Sony's [IBISS public description](https://pro.sony/en_ME/support-services/spare-parts/support-ibiss-spare-parts-ordering-system) links the same canonical `ibiss.crse.com` host and describes an account-based ordering system. Neither page exposes a SeusEX or W300 software package URL. The web browsing tool read the public text; direct PowerShell requests to these pro.sony pages returned 403.
6. Public search indexing of Sony SOMEA's `ASC Portal_Introduction_7.pdf`, page 54, shows an attachment labelled **`SeusEX_x64_128200.zip`** and a separate `SeusPFX_x64_14210.zip`. The screenshot describes old search results and newer software in portal attachment headers. It supplies no archive URL, no file bytes, and no model compatibility list. The indexed PDF URL carried a SAS-style query, which was not used. A request for the token-free public resource returned **HTTP 409**. This is evidence of an x64-named package, not an acquired x64 runtime and not W300 support.

## Archive checks and failure classification

All checks used normal HTTPS verification. Raw results are under `../downloads/ibiss-reference/`.

| Check | Actual result | Meaning / next action taken |
| --- | --- | --- |
| Broad wildcard CDX query for `*.crse.com/IBISS_Files/DSC/Software/*` | HTTP 503 | Archive endpoint transient failure; narrowed to exact known host/prefix. |
| CDX, `www.ibiss.crse.com/IBISS_Files/DSC/Software/`, prefix match, status 200 | HTTP 200, `[]` | No matching successful captures returned for this exact prefix. |
| CDX, `ibiss.crse.com/IBISS_Files/DSC/Software/`, prefix match, status 200 | HTTP 200, `[]` | Same successful empty index result on the canonical host. |
| CDX, `ibiss.crse.com/IBISS_Files/`, prefix match, status 200, URL containing Seus case-insensitively | HTTP 200, `[]` | No successful Seus-named capture under the broader observed file root. |
| Archive availability API for the www directory | HTTP 429 | Rate-limited; no repeated identical API request. Exact CDX results above completed the useful alternate route. |
| Sony's public one-page IBISS brochure, `https://pro.sony/s3/cms-static-content/file/65/1237493068365.pdf` | Public web parser reads one-page spare-parts availability statement; direct download 403 | Brochure, not software payload. No archive package established. |
| Actual HASP PDF hyperlink in the W270 thread | Cisco Secure Access Error 515: Upstream Certificate Untrusted | Source TLS trust failure. No TLS/proxy bypass attempted. This PDF would be driver documentation, not an Auto-Adj package. |

The linked HASP-document locator is `https://electronics-components.ru/files/2016/hasp_driver_win7_57129_110780_837.pdf`. No file bytes were saved from it.

One local result-saving helper initially treated a text CDX response as bytes. The HTTP response itself had succeeded with `[]`; the helper was corrected to save text, and that single request was repeated to preserve a reliable evidence file. It is a resolved local logging error, not a failed archive search.

## Reproducible local evidence

- `build/w300/downloads/ibiss-reference/forum-585578.html`: actual forum HTML; confirms plain-text locator and real HASP-document href.
- `endpoint-checks.json`: initial direct endpoint failures.
- `public-route-results.json`: brochure, token-free training PDF, archive availability result, and the explicitly corrected text-saving error.
- `cdx-known-prefix.json` and `cdx-known-prefix-result.json`: successful www-prefix CDX response and exact query.
- `canonical-host-results.json`: canonical host HTTP result and successful empty CDX queries.
- `canonical-host-route-0.txt`: actual canonical hostname redirect HTML.
- `canonical-host-route-1.txt`, `canonical-host-route-2.txt`: actual empty CDX JSON responses.
- `portal-results.json`: exact portal and observed legacy directory outcomes.
- `portal-route-0.html`: actual public Sony login page. No authenticated session material.

Example read-only replay of a completed archive check:

```powershell
Invoke-WebRequest -Uri 'https://web.archive.org/cdx/search/cdx?url=ibiss.crse.com/IBISS_Files/DSC/Software/&matchType=prefix&output=json&filter=statuscode:200&collapse=urlkey' | Select-Object StatusCode, Content
```

## Consequence for the Windows 10/11 x64 handoff

Do not package the previously acquired unsigned x86 WinRTUSB.sys as a working x64 driver. The new `SeusEX_x64_128200.zip` filename is a precise unresolved acquisition target, not a dependency that can be silently assumed to exist. Acquire the payload and inspect driver architecture/signature, W300 model support and HASP requirements. The Sony portal and filename are locators; derive W300 addresses, destination values and language operations from actual code or transactions.

The safe remaining avenues are an independently public copy of that exact package or of the exact W300 Auto-Adj bundle, or a demonstrated open implementation of the W300 protocol. Record the acquired files and dependencies in the current manifest, launch the actual program and qualify its model-specific operation before integrating it into the execution procedure.
