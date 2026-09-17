# Sony adjustment collection acquisition check

Editorial revision 4; underlying measurements and captured results retain their recorded scope.

Checked: 2026-09-16. Scope: three new collection/catalog routes, without a camera. No program was downloaded, executed or installed in this check. No useful public service-package locator was established.

The earlier `auto-adj-acquisition.md`, `seusex-public-acquisition-20260916.md` and `ibiss-acquisition.md` were consulted to exclude previously inspected Tekman, DAS, PlayStation utility, BVM, PMB and IBISS routes. Those earlier negative results were not counted as new tests.

## 1. Contemporary CD-ROM collection inventory

The Internet Archive advanced-search query `collection:cdromsoftware AND sony AND date:[2006-01-01T00:00:00Z TO 2012-12-31T23:59:59Z]` returned 60 records; all 60 were saved in `adjustment-collections-index.json`. This searches an actual software collection by period, rather than repeating the exact missing executable's name.

The public metadata and original-file inventories of three new camera-CD candidates were then retrieved and saved in `adjustment-collections-inventories.json`:

| Archive item | Actual original image listed | Finding from the item's description |
| --- | --- | --- |
| [Sony_A_DSLR_Picture_utilities](https://archive.org/details/Sony_A_DSLR_Picture_utilities) | `SONYPICTUTIL.ISO`, 284,491,776 bytes | 2007 alpha camera software: Picture Motion Browser, Image Data Lightbox SR, Image Data Converter SR and registration. |
| [sony-cyber-shot-dsc-t100](https://archive.org/details/sony-cyber-shot-dsc-t100) | `Cyber-shot DSC-T100 CD.iso`, 370,925,568 bytes | Consumer installation CD for DSC-T100, dated 2007. |
| [SonyHandycam](https://archive.org/details/SonyHandycam) | `SONYPICTUTIL.iso`, 513,265,664 bytes | 2009 camcorder CD: PMB 4.2.00, handbook and registration. |

These are real archived ISO objects, but their metadata supplies no service-tool or W300 linkage. The ISO bytes were not downloaded or inspected. Consequently this check does **not** assert that a member-by-member inspection proved Auto-Adj or SeusEX absent. There was no evidence justifying treating these unrelated consumer CDs as a service-software acquisition lead.

Classification: wrong product/package category in the retrieved descriptions; neither a missing runtime dependency nor demonstrated lack of W300 support in an acquired program.

## 2. Adjustment and imaging collection titles

The separate Internet Archive query `mediatype:software AND (title:("Digital Imaging") OR title:("Camera Service") OR title:("Adjustment Software"))` returned 15 records; all 15 are saved in `adjustment-collections-index.json`, with the exact API URL. The returned descriptions concern other vendors' consumer imaging products, unrelated collections or previously rejected non-Sony camera software. No Sony Digital Imaging Adjustment CD or W300 service package was identified in this result set.

Collection-oriented web searches using `Sony`, `adjustment software`, `CD-ROM`, `2008`, `Digital Imaging`, `AutoAdj` and `Auto Adj` produced manuals, consumer software and unrelated adjustment systems. These results supplied no additional public payload locator. A manual mentioning a CD or executable was not treated as that software.

Classification: no relevant artifact located within the queried public indexes. This is a bounded search result, not proof that no such collection exists elsewhere.

## 3. Contemporary primary Sony download catalog

Sony's [India Top Support Downloads catalog](https://www.sony.co.in/support/resources/en_AP/html/Usefulinfo/TopSupportTopics/TopSupportDownloads_IN.html), marked last updated 27 May 2009, was readable. Its digital-still-camera section lists consumer downloads such as Picture Motion Browser, normal USB drivers, printer software, Image Data Suite and Cyber-shot Viewer. The potentially promising wording “Display Adjustment software” belongs to the projector section. It therefore supplies no DSC service-tool package or missing W300/SeusEX endpoint.

Classification: a real Sony catalog, but its adjustment entry is for another product class. This was not an authentication or execution failure.

## Result and acquisition handoff

No `DSC-W300 Auto-Adj Ver_1.3r04.exe`, SeusEX executable or qualifying service collection was acquired. No empty download directory was created. The two saved JSON files preserve the newly examined archive records and file inventories for reproducibility; they are metadata evidence, not executable packages.

The three routes establish the search coverage above. The next acquisition task is to find a service-CD identifier or inspect a newly located service-collection manifest for W300/SeusEX, then retrieve and inspect any corresponding payload. Use the saved inventories to exclude these already reviewed consumer-CD descriptions. If a collection supplies no relevant lead, move to model-linked firmware or transaction acquisition in the [execution plan](../../../docs/w300/EXECUTION_PLAN.md). This closes the examined catalog queries, while acquisition and preparation of a validated original-board language operation continue.
