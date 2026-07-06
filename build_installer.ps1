param(
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================"
Write-Host " Sestaveni instalatoru - Generator zvuku"
Write-Host "============================================"
Write-Host ""

function Run-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][scriptblock]$Action,
        [string]$ErrorMessage = "Krok selhal."
    )

    Write-Host $Title
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

try {
    # Kontrola Pythonu
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "[CHYBA] Python neni nalezen v PATH. Nainstalujte Python z https://www.python.org a spuste skript znovu."
    }

    $pythonExe = $pythonCmd.Source

    $pythonVersion = (& $pythonExe --version) 2>&1
    Write-Host "Nalezen: $pythonVersion"
    Write-Host ""

    Run-Step -Title "[1/4] Instalace PyInstaller a Kivy zavislosti..." -Action {
        # Zajisti, ze pip je dostupny pro nalezeny Python interpreter.
        & $pythonExe -m ensurepip --upgrade | Out-Null
        & $pythonExe -m pip install --upgrade pip --quiet
        & $pythonExe -m pip install pyinstaller kivy_deps.sdl2 kivy_deps.glew --quiet
    } -ErrorMessage "[CHYBA] Instalace build zavislosti selhala."

    Run-Step -Title "[2/4] Instalace runtime zavislosti aplikace..." -Action {
        & $pythonExe -m pip install kivy edge_tts imageio_ffmpeg --quiet
    } -ErrorMessage "[CHYBA] Instalace runtime zavislosti selhala."

    Run-Step -Title "[3/4] Sestavuji aplikaci (muze trvat nekolik minut)..." -Action {
        & $pythonExe -m PyInstaller GeneratorZvuku.spec --noconfirm --clean
    } -ErrorMessage "[CHYBA] PyInstaller selhal."

    if (-not (Test-Path "dist\GeneratorZvuku\GeneratorZvuku.exe")) {
        throw "[CHYBA] Soubor dist\GeneratorZvuku\GeneratorZvuku.exe nebyl vytvoren."
    }

    Write-Host "[4/4] Hledam Inno Setup pro vytvoreni Setup.exe..."
    $isccCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($iscc) {
        Write-Host "Inno Setup nalezen, sestavuji Setup.exe..."
        & $iscc "installer.iss"
        if ($LASTEXITCODE -ne 0) {
            throw "[CHYBA] Inno Setup sestaveni selhalo."
        }

        if (Test-Path "installer_output\GeneratorZvukuSetup.exe") {
            Write-Host ""
            Write-Host "============================================"
            Write-Host " HOTOVO: installer_output\GeneratorZvukuSetup.exe"
            Write-Host "============================================"
        }
    }
    else {
        Write-Host "Inno Setup nenalezen - preskakuji tvorbu Setup.exe."
        Write-Host "Aplikace je pripravena v: dist\GeneratorZvuku\GeneratorZvuku.exe"
        Write-Host ""
        Write-Host "Pro vytvoreni jednosouboreho instalatoru:"
        Write-Host "  1. Stahni Inno Setup z https://jrsoftware.org/isinfo.php"
        Write-Host "  2. Spust tento skript znovu"
    }
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""
if (-not $NoPause) {
    Read-Host "Stiskni Enter pro ukonceni"
}
