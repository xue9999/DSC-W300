param(
    [ValidateSet('SelfTest','Inventory','Inquiry')][string]$Action = 'SelfTest',
    [string]$Serial
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Prepared Python environment is missing.' }
$script = Join-Path $PSScriptRoot 'w300_workbench.py'
switch ($Action) {
    'SelfTest' { & $python $script selftest }
    'Inventory' { & $python $script inventory }
    'Inquiry' {
        if (-not $Serial) { throw 'Supply the current serial reported by Inventory; historical serials are not accepted as evidence.' }
        & $python $script inquiry --serial $Serial
    }
}
exit $LASTEXITCODE
