# Baut eigenstaendige Windows-Versionen (ohne Python):
#   dist\dxf2qet-Setup-<version>.exe     Installer (Ordner-Build, startet schnell; ohne Adminrechte, Startmenue + optional Desktop)
#   dist\dxf2qet-<version>-portable.exe  Einzeldatei ohne Installation (entpackt sich bei jedem Start in %TEMP%)
#   .\build.ps1 -Ziel <ordner> -> portable EXE zusaetzlich dorthin kopieren
# Braucht Inno Setup 6 (winget install JRSoftware.InnoSetup --scope user)
param([string]$Ziel = "")
# kein ErrorActionPreference=Stop: PowerShell 5.1 haelt sonst uv-Fortschrittsmeldungen auf stderr fuer Fehler
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$uv = Get-Command uv -ErrorAction SilentlyContinue
$uvExe = if ($uv) { $uv.Source } else { (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv*\uv.exe" | Select-Object -First 1).FullName }
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 fehlt: winget install JRSoftware.InnoSetup --scope user" }
$version = (Select-String -Path "$root\src\dxf2qet\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value

$common = @(
    "--noconfirm", "--clean", "--windowed",
    "--name", "dxf2qet", "--icon", "$root\assets\icon.ico", "--add-data", "$root\assets\icon.ico;assets",
    "--paths", "$root\src", "--collect-data", "ezdxf",
    "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtQml", "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "PySide6.Qt3DCore", "--exclude-module", "PySide6.QtMultimedia", "--exclude-module", "PySide6.QtPdf",
    "--exclude-module", "matplotlib", "--exclude-module", "tkinter", "--exclude-module", "pytest",
    "--specpath", "build"
)

Push-Location $root
try {
    # alte Builds weg, damit nur Dateien dieser Version in dist\ liegen
    if (Test-Path dist) { Remove-Item dist\* -Force }
    New-Item -ItemType Directory -Force dist | Out-Null

    & $uvExe run --with pyinstaller pyinstaller @common --distpath build\dist --workpath build\work "$root\packaging\launcher.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller (Ordner) fehlgeschlagen" }
    & $iscc /Q "/DVersion=$version" "/DQuelle=$root\build\dist\dxf2qet" "$root\packaging\setup.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup fehlgeschlagen" }
    $setup = "dist\dxf2qet-Setup-$version.exe"

    & $uvExe run --with pyinstaller pyinstaller @common --onefile --distpath build\onefile --workpath build\work-onefile "$root\packaging\launcher.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller (Einzeldatei) fehlgeschlagen" }
    $exe = "dist\dxf2qet-$version-portable.exe"
    Copy-Item build\onefile\dxf2qet.exe $exe -Force

    if ($Ziel) { Copy-Item $exe $Ziel -Force }
    Get-Item $setup, $exe
} finally { Pop-Location }
