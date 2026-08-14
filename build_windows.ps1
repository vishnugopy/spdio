$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Building slim SongSplitter for Windows ..."
python -m PyInstaller --noconfirm SongSplitter.spec

if (Get-ChildItem -Recurse -Filter "*torch*" dist\SongSplitter -ErrorAction SilentlyContinue) {
    throw "torch leaked into the slim bundle"
}

$zip = "SongSplitter-win.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\SongSplitter\* -DestinationPath $zip
Write-Host "==> Done: $zip"
Get-Item $zip | Format-List Name, Length
