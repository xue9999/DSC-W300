# Rebuild the isolated Python 3.12 x64 environment solely from retained wheels.
param([string]$Python, [string]$EnvironmentName = 'venv')
$ErrorActionPreference = 'Stop'
if (-not $Python) { $Python = Join-Path $PSScriptRoot 'runtime\python312\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Restore the research asset to obtain runtime\python312\python.exe, or supply -Python.' }
& $Python -c 'import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32, "Python 3.12 x64 is required by the retained wheels"'
if ($LASTEXITCODE -ne 0) { throw 'Runtime version check failed.' }
if ($EnvironmentName -notmatch '^venv(?:-[A-Za-z0-9_-]+)?$') { throw 'Use venv or a venv- prefixed directory name.' }
$newEnvironment = Join-Path $PSScriptRoot $EnvironmentName
if (Test-Path -LiteralPath $newEnvironment) { throw 'Environment directory exists; use a new -EnvironmentName to preserve it.' }
& $Python -m venv $newEnvironment
if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed.' }
$newPython = Join-Path $newEnvironment 'Scripts\python.exe'
& $newPython -m pip install --no-index --find-links (Join-Path $PSScriptRoot 'wheels') -r (Join-Path $PSScriptRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Offline dependency installation failed.' }
& $newPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
$analysisSite = Join-Path $PSScriptRoot 're-tools\site'
& $newPython -m pip install --no-index --find-links (Join-Path $PSScriptRoot 're-tools\wheels') --target $analysisSite capstone==5.0.6
if ($LASTEXITCODE -ne 0) { throw 'Offline static-analysis dependency installation failed.' }
& $newPython (Join-Path $PSScriptRoot 'w300_workbench.py') selftest
exit $LASTEXITCODE
