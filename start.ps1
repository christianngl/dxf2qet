# Startet dxf2qet ohne Konsolenfenster.
# Mit Argumenten laeuft die Kommandozeile, z.B.:  .\start.ps1 plan.dxf --to qet
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv\Scripts"

if (-not (Test-Path (Join-Path $venv "python.exe"))) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { $uv = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv*\uv.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if (-not $uv) {
        Write-Host "uv nicht gefunden - installiere per winget ..."
        winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
        $uv = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv*\uv.exe" | Select-Object -First 1
    }
    $uvExe = if ($uv.Source) { $uv.Source } else { $uv.FullName }
    Write-Host "Erste Einrichtung: Python + Abhaengigkeiten werden installiert ..."
    & $uvExe sync --project $root
}

if ($args.Count -gt 0) {
    & (Join-Path $venv "python.exe") -m dxf2qet @args
} else {
    Start-Process -FilePath (Join-Path $venv "pythonw.exe") -ArgumentList "-m", "dxf2qet" -WorkingDirectory $root
}
