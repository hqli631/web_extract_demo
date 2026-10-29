$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$env:PYTHONPATH = Join-Path $project '.deps'
$python = Join-Path $project '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
& $python (Join-Path $project 'serve_review.py')
