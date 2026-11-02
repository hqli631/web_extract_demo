param([switch]$Collect, [switch]$OpenReport)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$candidates = @(
    (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
    'C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)
$projectPython = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $projectPython) { throw 'Python not found. Create .venv first.' }
$previousPythonPath = $env:PYTHONPATH
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONPATH = (Join-Path $PSScriptRoot '.deps')
    $env:PYTHONIOENCODING = 'utf-8'
    & $projectPython -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed.' }
    $validationArgs = @('check_development_cases.py')
    if ($Collect) { throw 'Use run_blind_validation.py --batch validation_blind_round2 --collect for a new frozen batch.' }
    & $projectPython @validationArgs
    if ($LASTEXITCODE -ne 0) { throw 'Validation report generation failed.' }
    if ($OpenReport) { Start-Process (Join-Path $PSScriptRoot 'reports\development_cases\progress.html') }
    Write-Host 'Done: reports/development_cases/progress.html'
} finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:PYTHONIOENCODING = $previousEncoding
}
