# Baut eine eigenstaendige Windows-Version (ohne Python) und packt sie als ZIP.
#   .\build.ps1                -> dist\dxf2qet-<version>-win64.zip
#   .\build.ps1 -Ziel <ordner> -> ZIP zusaetzlich dorthin kopieren
param([string]$Ziel = "")
# kein ErrorActionPreference=Stop: PowerShell 5.1 haelt sonst uv-Fortschrittsmeldungen auf stderr fuer Fehler
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$uv = Get-Command uv -ErrorAction SilentlyContinue
$uvExe = if ($uv) { $uv.Source } else { (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv*\uv.exe" | Select-Object -First 1).FullName }
$version = (Select-String -Path "$root\src\dxf2qet\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value

Push-Location $root
try {
    & $uvExe run --with pyinstaller pyinstaller --noconfirm --clean --windowed `
        --name dxf2qet --icon "$root\assets\icon.ico" --add-data "$root\assets\icon.ico;assets" `
        --paths "$root\src" --collect-data ezdxf `
        --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
        --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf `
        --exclude-module matplotlib --exclude-module tkinter --exclude-module pytest `
        --distpath build\dist --workpath build\work --specpath build `
        "$root\packaging\launcher.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen" }
    Copy-Item README.md build\dist\dxf2qet\LIESMICH.md
    New-Item -ItemType Directory -Force dist | Out-Null
    $zip = "dist\dxf2qet-$version-win64.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path build\dist\dxf2qet -DestinationPath $zip
    if ($Ziel) { Copy-Item $zip $Ziel -Force }
    Get-Item $zip
} finally { Pop-Location }
