# Historical Sony Japan body-update catalog: bounded acquisition

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

Checked 2026-09-17. No camera was connected, no software package was executed, and no login, external contact or purchase occurred. Original `sources/` and `evidence/` files remained unchanged.

## Actual outcome

Sony Japan's historical body-update catalog and archived pages reached through its relocation notice were inspected. Their model lists and HTML are retained below. Continue acquisition of DSC-W300 proprietary firmware or `DSC-W300 Auto-Adj Ver_1.3r04.exe` through a new model-linked package source, then verify actual executable contents.

Prior acquisition reports (`auto-adj-acquisition.md`, `adjustment-collections.md`, `seusex-public-acquisition-20260916.md`, `w300-package-followup.md`, `w300-firmware-followup.md`, and `downloads/w300-firmware-candidates/ACQUISITION_REPORT.md`) were reviewed. Initial discovery searches reproduced several known irrelevant/manual hits and are not counted as new evidence. The `bbs.520101.com` historical archive was excluded from this check because a separate investigation covered it.

## New source chain and inspected content

1. [Sony Japan's historical Cyber-shot notices](https://www.sony.jp/support/cyber-shot/whatsnew/past.html) retain an entry dated 15 May 2008 announcing W300 product support. It points to the ordinary W300 product page, whose downloaded HTML now contains a redirect to the current support site. That announcement supplies no updater filename. The same notices contain a distinct firmware-catalog relocation announcement dated 30 November 2010.
2. [Sony's 30 November 2010 relocation notice](https://www.sony.jp/cyber-shot/info2/20101130.html) explicitly links the body-update section at `support.d-imaging.sony.co.jp/www/cyber-shot/update/index.html`. The live target returned 404 through the web tool, so the next action was to retrieve exact historical CDX captures. This is an unavailable live page, not a runtime or dependency failure. CDX returned twelve successful, distinct-digest captures. Both the earliest (2010-12-01) and latest returned capture (2014-02-06) were downloaded as actual HTML.
3. The archived catalog links to `2009.html` and `past.html`; their exact CDX indices and first successful captures were then acquired. The 2010 catalog lists HX5V and TJS-1 updates. Its 2009 page lists G3. Its older-updates page lists R1, F828 and T1 entries, with dates in 2004–2005. The 2014 index lists QX100/QX10. None of these four inspected body-update pages contains W300. Thus no body-update link for W300 can be followed from these inspected pages. This does not prove that no service-only W300 firmware exists or that every historical catalog version was inspected.

The original Japanese text was decoded as CP932/Shift_JIS for inspection, matching the response metadata. Firmware entries were extracted from the actual `update_news` block, not inferred from general support-page titles. Returned page bytes and SHA-256 values are retained in acquisition receipts.

## Files and reproduction

Acquired material: `build/w300/downloads/w300-package-source/`.

- `acquire.py`: bounded public GETs for the primary notices, relocation page, current redirect page, and exact catalog CDX index.
- `follow_catalog.py`: retrieves the first/last successful catalog captures from that returned index.
- `follow_years.py`: follows only the two actual older-year links from the retrieved catalog.
- `inspect_catalog.py`: verifies all ten successfully saved responses offline against acquisition receipts and extracts the four archived update blocks and their links.
- `inspection.json`: successful offline inspection result; acquisition errors are kept separate from saved payloads.

Run the offline check from the repository root:

```powershell
& build/w300/venv/Scripts/python.exe build/w300/reports/w300-package-source/inspect_catalog.py
```

Network replay scripts are preserved separately and need not be rerun to reproduce the content-based conclusion. No executable/archive payload was discovered or downloaded.

## Completed catalog coverage and next acquisition route

The inspected catalogs establish which model entries those pages contain. Pursue a new model-linked W300 package or trace locator, inspect its payload and verify the model from internal evidence. Reuse saved catalogs instead of repeating the same queries.

The next task is to locate and acquire a model-linked W300 service package, proprietary firmware image, or sufficiently documented W300 communication trace, recording provenance and actual bytes. The exact Auto-Adj route additionally requires usable SeusEX and any required legitimate HASP access. If that route cannot currently supply bytes, continue through the firmware/trace and file-acquisition preparation routes in the [execution plan](../../../../docs/w300/EXECUTION_PLAN.md). Evaluate each obtained artifact for retail-board eligibility, language addresses, persistence and restoration; the catalog HTML remains evidence of search coverage rather than an implementation source.
