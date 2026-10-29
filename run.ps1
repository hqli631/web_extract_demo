$ErrorActionPreference = "Stop"
$python = "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $project ".deps"
& $python (Join-Path $project "extract.py")
if ($LASTEXITCODE -eq 0) { & $python (Join-Path $project "build_review.py") }
if ($LASTEXITCODE -eq 0) { Copy-Item (Join-Path $project "visual_review.html") (Join-Path $project "output\visual_review.html") -Force }
