# W300 manual-watermark archive follow-up

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

## Result

A real public archive of the previously unresolved `bbs.520101.com` watermark source was accessed. The saved CDX response contains 4707 distinct successful URL captures (query limit 5000). It includes the actual camera forum, Sony/ADJ tags and attachment-list page. The camera forum lists **Sony DSC W300_L3 V1.1** at `thread-5681-1-1.html`; it describes the Level-3 manual, not software. Use the recovered archive structure to pursue a model-specific binary, language transaction or Auto-Adj payload from a new concrete locator.

This is a new primary forum-index observation, not an exhaustive statement about all historical/private attachments.

## Sources inspected

- https://web.archive.org/web/20090802184538id_/http://bbs.520101.com:80/forum-163-1.html — W300 L3 title and exact thread link; neighboring records are camera service manuals.
- https://web.archive.org/web/20090802184546id_/http://bbs.520101.com:80/forum-163-2.html — second saved camera-manual page.
- https://web.archive.org/web/20091001101427id_/http://bbs.520101.com:80/tag-ADJ.html — only displayed thread is F828 Level1/Level2/ADJ, a different camera/manual listing.
- https://web.archive.org/web/20091001071831id_/http://bbs.520101.com:80/tag-SONY.html — mixed Sony repair/manual topics; not a W300 executable.
- https://web.archive.org/web/20110510000328id_/http://bbs.520101.com:80/attachmentList.php — first attachment page contains television BIN/PDF records. It advertises 1174 pages; those were not all captured or inspected, so this check does not establish whether other attachments contain the software.

The 4707-row successful-capture index contains no archive/binary MIME type and no W300-bearing URL, but numeric thread/attachment URLs prevent treating that fact as a complete content search. The displayed W300 thread was followed with an exact-prefix CDX lookup **without** a status filter; the response was empty. No thread body or attachment URL was recovered.

## Failure classification and alternatives actually tried

- Earlier direct `bbs.520101.com` failure was an availability problem. The archived-domain CDX query succeeded and supplied real pages, so that alternative was executed rather than left as a suggestion.
- The separate archive availability endpoint returned HTTP 429. It was not repeatedly queried; the already successful CDX route provided timestamped records directly.
- The live `https://www.520101.com/` address failed hostname certificate validation. The original public `http://www.520101.com/` link from the forum was then fetched normally; it returned a 63-byte placeholder with no link, not the old forum. Certificate verification was not disabled.
- None of these is a Python/dependency/driver error or a demonstrated lack of W300 support. The remaining problem is absence of an inspectable W300 service implementation or transaction source in the inspected material.

## Retained evidence

Raw CDX/HTML responses, URLs, HTTP results and hashes are under `build/w300/downloads/w300-watermark-archive/`. GBK pages were decoded with Python `gb18030`; the parser retained actual link labels and targets in `camera-forum-links.json`. `verified-index.json` checks row count, content types, the exact W300 title/link, empty thread query and acquired-file hashes. The existing W300 L3 PDF was not downloaded again. No camera or firmware execution occurred.

Reuse these exact archived pages as completed search coverage. Search for a different thread, mirror or attachment inventory and verify any W300-linked binary from its actual contents. If no distinct archive lead emerges, move to the other package/firmware routes and file-acquisition preparation in the [execution plan](../../../../docs/w300/EXECUTION_PLAN.md). The manual listing remains a source locator; executable behavior, device mapping and production-board eligibility require their own evidence.
