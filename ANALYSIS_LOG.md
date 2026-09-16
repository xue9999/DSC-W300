# DSC-W300 durable project guidance

## Goal and constraints

Make the original Japanese DSC-W300 retain English menus. Enclosure stays closed. Mac preferred; Windows 11 PC available. Preserve identity/calibration. No cross-model payloads, blind destination bytes, board transplant, or unrelated adjustments. Physical English persistence is the completion criterion.

## Authoritative evidence and corrected decisions

- `sources/sony_dsc-w300_adjustment_ver1.3.pdf`: Sony 9-852-287-54, 37 pages. PDF p. 11 / printed 6-10 explicitly restricts Destination Data Write to service boards.
- Exact program: `DSC-W300 Auto-Adj Ver_1.3r04.exe` (pp. 1, 9). HASP key + SeusEX and Windows 2000/XP documented (pp. 3, 30). Exact driver/SeusEX versions unresolved.
- AEP is an area, not dropdown destination. Prefer CEE8: English initial, Polish selectable, PAL. CEE9 also English initial with Russian selectable. J1 is Japanese-only. Actual device destination requires reading.
- Destination completion dialog automatically resets camera after OK. Source screenshot p. 11 controls this detail; extracted text omits dialog contents.
- Backup p. 36 covers video/LCD/camera adjustment data. Do not claim destination/full-flash coverage or rollback from that alone.
- CONNECT changes mode (pp. 9-10). END releases mode. The documented setup uses AC-LS5/DC reconnection; do not invent a battery substitute.
- Aging pp. 33-35 can format media/reset counters and is excluded.

## Proven tools and routes

- Bundled Python pypdf extracts text; pypdfium2 renders pages. No software attachments in recovered ADJ PDF.
- Elektrotanya automated retrieval returned 403; normal browser reached CAPTCHA. User downloaded exact PDF. Do not repeatedly retry blocked automated URL.
- `tools/w300_evidence.py inventory`: passive macOS ioreg parsing, Sony-only details, no device handles/vendor requests. Exclusive output creation.
- `compare`: offline complete-byte comparison, hashes, bounded offset list; no normalization, no camera access. Equality does not establish coverage. Require nonempty captures independently.
- `sources/Sony-PMCA-RE` is an upstream source snapshot, not executed or W300-validated. Stock info calls updater init; serviceshell switches/authenticates. Do not label these passive.

## Retry and stop rules

Missing executable triggers acquisition/offline analysis. Service-board limitation triggers investigation, not an unvalidated write. No hardware-dependent work without visible camera. No repeated identical failed search route without a new lead. New camera input justifies refreshing inventory. Preserve source originals and capture files. `sources/manifest.json` and `evidence/` hold recoverable hashes/results; keep this log free of run chronology.

- PMCA backup parser supports BK2/BK4; neither that format nor its language-property addresses are established for W300. See `evidence/usb-investigation.md` before further USB work.
- If system Python TLS lacks a CA chain, use bundled Python with verification enabled; do not disable certificate verification.
- `tools/w300_service_tool.py` and `docs/w300/SERVICE_PROTOCOL_SPEC.md` contain unvalidated W300-specific claims despite authoritative wording. Generic PMCA properties and a matching mock do not establish W300 destination encoding or retail-board eligibility. Do not treat passing mock tests as hardware qualification.
- Service-tool `detect` now delegates to passive registry inventory; `--dry-run` uses only a mock without initializing libusb. Live service CLI commands are rejected pending model-specific qualification. The original implementation did not meet these guarantees; see `evidence/w300/CEE8_PREFLIGHT_REVIEW_20260916.md` for the pre-repair review.
- Generic PMCA property `0x01070148` is `palNtscSelector`, not proof of a PAL output-mode byte. Upstream Senser flow authenticates on the initial interface before re-enumeration; the experimental W300 transport's reverse order is unqualified. Require recoverable baseline and post-restart persistence verification before qualifying a conversion route.
