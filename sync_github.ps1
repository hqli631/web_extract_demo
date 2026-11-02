$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git was not found. Install Git and restart this window.'
    }
    $branch = & git branch --show-current
    if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') {
        throw 'The current branch must be main. No changes were staged.'
    }
    $remote = & git remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote -ne 'https://github.com/hqli631/web_extract_demo.git') {
        throw 'The origin URL is not the expected project repository. No changes were staged.'
    }
    Write-Host "Repository: $remote"
    Write-Host 'Staging project changes (except ignored files)...'
    & git add -A
    if ($LASTEXITCODE -ne 0) { throw 'Git could not stage changes.' }
    & git diff --cached --quiet
    $diffResult = $LASTEXITCODE
    if ($diffResult -eq 1) {
        $message = 'Project update ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        & git commit -m $message
        if ($LASTEXITCODE -ne 0) { throw 'Commit failed. Push was not attempted.' }
    } elseif ($diffResult -ne 0) {
        throw 'Git could not inspect staged changes.'
    } else {
        Write-Host 'No new changes to commit; checking for commits to push.'
    }
    & git -c http.sslBackend=openssl -c http.version=HTTP/1.1 push -u origin main
    if ($LASTEXITCODE -ne 0) {
        throw 'Push failed. Local commits remain saved. Check the error above and retry.'
    }
    Write-Host 'Sync succeeded.' -ForegroundColor Green
} catch {
    Write-Host "Sync failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
