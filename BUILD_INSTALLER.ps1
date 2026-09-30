$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host 'Cassette Windows installer build' -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python Launcher (py) was not found on the BUILD MACHINE.'
}

py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

py -m PyInstaller --noconfirm --clean Cassette.spec

$isccCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw 'Inno Setup 6 was not found on the BUILD MACHINE.'
}

if (Test-Path installer_output) { Remove-Item installer_output -Recurse -Force }
& $iscc (Join-Path $PWD 'installer.iss')

Write-Host "DONE: $(Join-Path $PWD 'installer_output\Cassette_Setup.exe')" -ForegroundColor Green
