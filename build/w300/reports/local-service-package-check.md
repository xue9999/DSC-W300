# Local Downloads service-package check

Editorial revision 5; underlying measurements and captured results retain their recorded scope.

Date: 2026-09-16.

Checked only `C:\Users\apara01\Downloads`, first its top level and then recursively within that directory. The directory is accessible. No profile-wide search, network request, file copy, modification of originals, installation, or execution was performed. No symbolic-link traversal was requested.

Case-insensitive filename and directory-name filter:

```text
DSC[-_ ]?W300 | W300 | Seus | Auto[-_ ]?Adj | HASP |
Sony.*(service|adjust) | (service|adjust).*Sony
```

The actual combined regular expression is recorded in the reproduction command below. Matching was limited to task-related names; unrelated user filenames were neither reported nor saved.

**Result: zero matching files, zero matching directories, zero enumeration errors.** No candidate archive or binary was available for static inspection. This completes the Downloads filename check within its stated scope; archives with unrelated names could still contain service software.

Machine-readable result: `build/w300/reports/local-service-package-matches.json`.

Read-only reproduction of the file check:

```powershell
Get-ChildItem -LiteralPath 'C:\Users\apara01\Downloads' -File -Recurse -Force |
  Where-Object { $_.Name -match '(?i)(DSC[-_ ]?W300|W300|Seus|Auto[-_ ]?Adj|HASP|Sony.*(service|adjust)|(service|adjust).*Sony)' } |
  Select-Object FullName, Name, Length, LastWriteTime, Extension
```

Classification: no candidate matching the authorized filename scope, rather than an inaccessible folder or a tool/runtime failure. No locally existing W300 Auto-Adj, SeusEX, HASP, or Sony service/adjustment package was discovered by this check. Continue external package/firmware acquisition or file-transfer preparation in the [execution plan](../../../docs/w300/EXECUTION_PLAN.md). Revisit this filename inventory when new task-related files arrive; a wider search of unrelated personal directories is not the automatic next step.
