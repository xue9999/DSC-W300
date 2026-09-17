# G3 / W300 service-manual cross-check: source coverage and acquisition task

Editorial revision 4; underlying measurements and captured results retain their recorded scope.

## Outcome

No actual DSC-G3 adjustment manual or Sony-authored G3 SEUS table was acquired in this bounded follow-up. Consequently **the intended G3-to-W300 manual comparison has not been completed**. No G3 Block/Page/Address value, destination operation, original-board eligibility rule or two-byte-address convention is attributed to a Sony G3 manual here.

The W300 anchor remains the already reviewed Sony ADJ page 30: Block `11`, Page `61`, Address `0E10` and `0E11`, used for the stabilization Dp/Dy checks. The retained G3 binary's page8/address16 handler is separate static evidence. Numerical resemblance between a G3 table entry and those W300 calibration addresses does not connect Sony's GUI fields to an outer USB packet, nor establish that their meanings agree between models.

## Local coverage before web research

Targeted file/path searches in `sources/`, `evidence/` and `build/w300/downloads/` found no existing G3 service PDF or extracted service-manual text. Relevant Markdown searches found the existing G3 receiver/fallback analysis and its express cross-model limits, not a previous G3 manual acquisition. Firmware sections and end-user manuals were not treated as an ADJ manual.

## Concrete public locators checked

| Locator | Actual result | What it proves |
| --- | --- | --- |
| [Ultimate Service Manuals Sony collection](https://www.ultimateservicemanuals.com/products/sony-ultimate-digital-camera-repair-service-manuals-dsc-nex-dslr-a700-a900) | Visible DVD catalog lists `DSC-G3 ADJ v1.2`, plus G3 L2/L3 v1.2. It offers a paid collection, not publicly readable manual pages. | A specific catalog lead only. No PDF contents, Sony document number or field semantics were verified. No purchase/contact was made. |
| [Vinafix G3 service-manual listing](https://vinafix.com/threads/sony-dsc-g3-service-manual.39454/) | Visible listing has G3 L2/L3 v1.2 PDFs; the live page explicitly marks their download access as requiring paid membership. Direct landing-page retrieval by Python returned 403, while the web tool read the listing. | Attachment metadata only. No login, attachment access bypass or download was attempted after the access requirement was visible. |
| [pdf-manuals G3 listing](https://pdf-manuals.ru/sony/dsc_g3_manuals.html) | Indexed text names `sony_dsc_g3_manuals.pdf` and generically advertises user/service/repair material. Both base and www landing hosts returned HTTP 500 to direct retrieval. The web open also failed. | An unverified filename; there is no demonstrated service content. The public-page Wayback CDX request timed out. |
| Internet Archive exact-model catalog | A successful metadata request for the exact phrase DSC-G3 returned six records: end-user handbook/instruction/information material and PMB. The response is retained. Broader catalog queries did not produce a verified service-document candidate. | Search result only; no absence claim about the Internet Archive as a whole. |
| Parts Town model-manual candidate | `SONY-DSCG3_sm.pdf`, inferred from an independently indexed G1 service-manual path pattern, returned 403. | No existence or contents claim. It was a candidate URL, not an observed G3 file link. |
| Encompass service-document candidates | Both `/SON/sm/DSCG3.pdf` and `/SON/rr/DSCG3.pdf` returned HTTP 451. | No existence or contents claim. Candidate paths were not validated as G3 documents. |
| Other public service indexes | The G3 eserviceinfo search request returned 403; the servlib model candidate returned 502; the servicemanuals.us model candidate failed TLS negotiation. | Host/access failures, not a technical finding about camera support. TLS verification was not disabled. |

The normal browser fallback could not be used because the computer-use tool reported no available browser. The network research itself remained possible through web search and successful ordinary HTTPS requests to Internet Archive. This is not a camera-connection limitation or a missing Python dependency.

Model-qualified searches covered the exact model, `DSC-G3_ADJ`, `Auto-Adj`, `SeusEX`, `DESTINATION DATA WRITE`, `0E10`, service/manual variants and the newly found v1.2 catalog designation. They did not expose a Sony G3 service table. Search results for G1, unrelated G3 products, end-user Auto Adjustment mode and other camera service manuals were not substituted.

## Retained records and next evidentiary requirement

All new files are confined to `build/w300/downloads/g3-service-reference/` and this report directory. `candidate-acquisition.json`, `catalog-acquisition.json` and `archive-acquisition.json` preserve concrete request URLs and results. The successful Internet Archive JSON responses are retained; `local-artifacts.json` records their sizes and hashes. `search-receipts.json` records the web-readable catalog locators, access restrictions and classification, without claiming downloaded source documents.

To complete this comparison, locate and acquire an actual G3 ADJ v1.2 document or equivalent Sony-authored service fragment showing its field names and concrete tuple. Use the exact catalog designation to search a distinct accessible source; repeat a failed endpoint only when access conditions or its locator change. Compare the acquired printed table and operation context first, then test whether the static receiver independently explains the tuple. A numerical resemblance such as `61` or `0E10` alone does not establish W300 equivalence. This comparison is optional support: continue W300 package/trace acquisition and file-transfer preparation under the [execution plan](../../../../docs/w300/EXECUTION_PLAN.md) if the G3 document remains inaccessible.

No G3 service PDF was downloaded, no PDF was rendered for this follow-up, and no manual-based G3 comparison result is claimed. No main documentation or ANALYSIS_LOG was changed; no USB, service-mode, camera read or camera write was performed.
