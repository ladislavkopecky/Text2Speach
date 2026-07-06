$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================"
Write-Host " Cleanup poškozenych pip metadat (~ip)"
Write-Host "============================================"
Write-Host ""

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[CHYBA] Python neni nalezen v PATH." -ForegroundColor Red
    exit 1
}

$pythonExe = $pythonCmd.Source
$sitePackages = (& $pythonExe -c "import sysconfig; print(sysconfig.get_path('purelib'))")

if (-not (Test-Path $sitePackages)) {
    Write-Host "[CHYBA] Site-packages nenalezen: $sitePackages" -ForegroundColor Red
    exit 1
}

Write-Host "Python: $pythonExe"
Write-Host "Site-packages: $sitePackages"
Write-Host ""

$targets = Get-ChildItem -LiteralPath $sitePackages -Force |
    Where-Object { $_.Name -like '~ip*' -or $_.Name -like '*~ip*' }

if (-not $targets -or $targets.Count -eq 0) {
    Write-Host "Nebyly nalezeny zadne polozky ~ip. Neni co cistit."
    exit 0
}

Write-Host "Nalezeny podezrele polozky:"
$targets | ForEach-Object { Write-Host (" - " + $_.FullName) }
Write-Host ""

foreach ($item in $targets) {
    try {
        Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop
        Write-Host "Smazano: $($item.FullName)"
    }
    catch {
        Write-Host "[CHYBA] Nepodarilo se smazat: $($item.FullName)" -ForegroundColor Red
        Write-Host "        $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Hotovo. Obnovuji pip..."
& $pythonExe -m ensurepip --upgrade | Out-Null
& $pythonExe -m pip install --upgrade pip --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "[CHYBA] Obnova pip selhala." -ForegroundColor Red
    exit 1
}

Write-Host "Cleanup dokoncen. Varovani 'Ignoring invalid distribution ~ip' by mela zmizet." -ForegroundColor Green
