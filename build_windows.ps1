$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Building slim Spdio for Windows ..."
python -m PyInstaller --noconfirm SongSplitter.spec

if (Get-ChildItem -Recurse -Filter "*torch*" dist\Spdio -ErrorAction SilentlyContinue) {
    throw "torch leaked into the slim bundle"
}

$zip = "Spdio-win.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\Spdio\* -DestinationPath $zip
Write-Host "==> Done: $zip"
Get-Item $zip | Format-List Name, Length
