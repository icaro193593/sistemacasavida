param(
    [switch]$SemAtalho,
    [switch]$NaoIniciar,
    [switch]$NaoPausar,
    [switch]$SemTarefa
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Test-PythonExecutable {
    param([string]$ExePath)

    if ([string]::IsNullOrWhiteSpace($ExePath)) {
        return $false
    }
    $ExePath = $ExePath.Trim()
    if ($ExePath -like "*\WindowsApps\*") {
        return $false
    }
    if (-not (Test-Path -LiteralPath $ExePath)) {
        return $false
    }

    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $ExePath -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prevEAP
    }
}

function Get-PythonVersionNumber {
    param([string]$FolderName)

    if ($FolderName -match 'Python(\d)(\d+)') {
        return ([int]$Matches[1] * 1000) + [int]$Matches[2]
    }
    return 0
}

function Find-Python3 {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # 1. Launcher py -3
        $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($null -ne $pyLauncher) {
            $pyResolved = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($pyResolved)) {
                $candidate = ($pyResolved | Select-Object -First 1).Trim()
                if (Test-PythonExecutable -ExePath $candidate) {
                    return $candidate
                }
            }
        }

        # 2. Instalações padrão no Windows (usuário e sistema, mais recente primeiro)
        $searchRoots = @(
            (Join-Path $env:LocalAppData "Programs\Python"),
            "C:\Program Files",
            "C:\Program Files (x86)"
        )
        foreach ($root in $searchRoots) {
            if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root)) {
                continue
            }
            $dirs = Get-ChildItem -LiteralPath $root -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
                Sort-Object { Get-PythonVersionNumber $_.Name } -Descending
            foreach ($dir in $dirs) {
                $exe = Join-Path $dir.FullName "python.exe"
                if (Test-PythonExecutable -ExePath $exe) {
                    return $exe
                }
            }
        }

        # 3. Comandos python / python3 no PATH (ignorando WindowsApps)
        foreach ($cmdName in @("python", "python3")) {
            $cmds = Get-Command $cmdName -All -ErrorAction SilentlyContinue
            foreach ($cmd in $cmds) {
                if ($cmd.Source -and (Test-PythonExecutable -ExePath $cmd.Source)) {
                    return $cmd.Source
                }
            }
        }

        return $null
    } finally {
        $ErrorActionPreference = $prevEAP
    }
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   Instalador - Sistema Casa Vida" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Pasta do sistema: $ProjectRoot"
Write-Host ""

# ---------------------------------------------------------
# Etapa 1 - Localizar ou instalar Python 3
# ---------------------------------------------------------
Write-Host "[1/6] Verificando Python 3..." -ForegroundColor Cyan
$PythonExe = Find-Python3

if ($null -eq $PythonExe) {
    Write-Host "[INFO] Python 3.8+ não encontrado. Tentando instalar automaticamente..." -ForegroundColor Yellow

    $osVer = [Environment]::OSVersion.Version
    $isWin7 = ($osVer.Major -eq 6 -and $osVer.Minor -eq 1)
    $is64 = [Environment]::Is64BitOperatingSystem

    if (-not $isWin7) {
        $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
        if ($null -ne $wingetCmd) {
            Write-Host "[INFO] Tentando instalar Python 3.12 via winget (escopo do usuário)..."
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                & winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
            } catch {
                Write-Host "[AVISO] Falha ao usar winget: $($_.Exception.Message)" -ForegroundColor Yellow
            } finally {
                $ErrorActionPreference = $prevEAP
            }
            $PythonExe = Find-Python3
        }
    }

    if ($null -eq $PythonExe) {
        if ($isWin7) {
            $pyVersion = "3.8.10"
            $installerFile = if ($is64) { "python-3.8.10-amd64.exe" } else { "python-3.8.10.exe" }
        } else {
            $pyVersion = "3.12.8"
            $installerFile = if ($is64) { "python-3.12.8-amd64.exe" } else { "python-3.12.8.exe" }
        }

        $downloadUrl = "https://www.python.org/ftp/python/$pyVersion/$installerFile"
        $tempInstaller = Join-Path $env:TEMP "python_installer_casavida.exe"

        Write-Host "[INFO] Baixando instalador oficial do Python $pyVersion ($installerFile)..."
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $downloadUrl -OutFile $tempInstaller -UseBasicParsing
            Write-Host "[INFO] Instalando Python $pyVersion silenciosamente para o usuário atual..."
            $proc = Start-Process -FilePath $tempInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0" -Wait -PassThru
            if ($proc.ExitCode -ne 0) {
                Write-Host "[AVISO] Instalador retornou código $($proc.ExitCode)." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[ERRO] Não foi possível baixar/instalar o Python automaticamente: $($_.Exception.Message)" -ForegroundColor Red
        } finally {
            if (Test-Path -LiteralPath $tempInstaller) {
                Remove-Item -LiteralPath $tempInstaller -Force -ErrorAction SilentlyContinue
            }
        }

        $PythonExe = Find-Python3
    }

    if ($null -eq $PythonExe) {
        Write-Host ""
        Write-Host "[ERRO] Não foi possível localizar nem instalar o Python 3.8+." -ForegroundColor Red
        Write-Host "Verifique sua conexão com a internet ou instale manualmente em https://www.python.org/downloads/ e execute instalar.bat novamente." -ForegroundColor Red
        exit 1
    }
}

$pyVersionLabel = (& $PythonExe --version 2>&1 | Out-String).Trim()
Write-Host "[OK] Python pronto: $PythonExe ($pyVersionLabel)" -ForegroundColor Green

# ---------------------------------------------------------
# Etapa 2 - Criar venv\ e instalar requirements.txt
# ---------------------------------------------------------
Write-Host "[2/6] Configurando ambiente virtual (venv) e dependências..." -ForegroundColor Cyan
$VenvDir = Join-Path $ProjectRoot "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "[INFO] Criando ambiente virtual em $VenvDir..."
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonExe -m venv "$VenvDir"
        $venvExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEAP
    }
    if ($venvExit -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
        Write-Host "[ERRO] Falha ao criar o ambiente virtual Python." -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path -LiteralPath $RequirementsPath)) {
    Write-Host "[ERRO] Arquivo requirements.txt não encontrado em $ProjectRoot." -ForegroundColor Red
    exit 1
}

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $VenvPython -m pip install -r "$RequirementsPath" --disable-pip-version-check
    $pipExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $prevEAP
}

if ($pipExit -ne 0) {
    Write-Host ""
    Write-Host "[ERRO] Falha ao instalar dependências do requirements.txt." -ForegroundColor Red
    Write-Host "Se este computador estiver sem acesso à internet, conecte-se e execute instalar.bat novamente." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Ambiente virtual e dependências verificados." -ForegroundColor Green

# ---------------------------------------------------------
# Etapa 3 - Verificar .env
# ---------------------------------------------------------
Write-Host "[3/6] Verificando arquivo de configuração (.env)..." -ForegroundColor Cyan
$EnvPath = Join-Path $ProjectRoot ".env"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"

if (Test-Path -LiteralPath $EnvPath) {
    Write-Host "[OK] Arquivo .env encontrado e preservado." -ForegroundColor Green
} elseif (Test-Path -LiteralPath $EnvExamplePath) {
    Copy-Item -LiteralPath $EnvExamplePath -Destination $EnvPath
    Write-Host "[AVISO] Arquivo .env criado a partir do .env.example. Preencha o Google Sheets e o SMTP antes de usar sincronizacao/backup por e-mail." -ForegroundColor Yellow
} else {
    Write-Host "[AVISO] Arquivo .env não encontrado e .env.example ausente." -ForegroundColor Yellow
}

# ---------------------------------------------------------
# Etapa 4 - Registrar tarefa semanal no Agendador do Windows
# ---------------------------------------------------------
Write-Host "[4/6] Configurando tarefa de backup semanal no Agendador do Windows..." -ForegroundColor Cyan
$TaskScript = Join-Path $ProjectRoot "scripts\instalar_tarefa_backup.ps1"

if ($SemTarefa) {
    Write-Host "[INFO] Registro da tarefa semanal ignorado (-SemTarefa)." -ForegroundColor Yellow
} elseif (Test-Path -LiteralPath $TaskScript) {
    try {
        & $TaskScript
    } catch {
        Write-Host "[AVISO] Não foi possível registrar a tarefa semanal automaticamente: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[AVISO] Script instalar_tarefa_backup.ps1 não encontrado; etapa ignorada." -ForegroundColor Yellow
}

# ---------------------------------------------------------
# Etapa 5 - Criar atalho Sistema Casa Vida.lnk na Área de Trabalho
# ---------------------------------------------------------
Write-Host "[5/6] Criando atalho na Área de Trabalho..." -ForegroundColor Cyan
if ($SemAtalho) {
    Write-Host "[INFO] Criação de atalho ignorada (-SemAtalho)." -ForegroundColor Yellow
} else {
    try {
        $DesktopDir = [Environment]::GetFolderPath('Desktop')
        $ShortcutPath = Join-Path $DesktopDir "Sistema Casa Vida.lnk"
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = Join-Path $ProjectRoot "iniciar.bat"
        $Shortcut.WorkingDirectory = $ProjectRoot
        $Shortcut.WindowStyle = 7

        $IconCasaVida = Join-Path $ProjectRoot "app\static\img\casa_vida.ico"
        $IconFavicon = Join-Path $ProjectRoot "app\static\img\favicon.ico"
        if (Test-Path -LiteralPath $IconCasaVida) {
            $Shortcut.IconLocation = "$IconCasaVida,0"
        } elseif (Test-Path -LiteralPath $IconFavicon) {
            $Shortcut.IconLocation = "$IconFavicon,0"
        }

        $Shortcut.Description = "Iniciar Sistema Casa Vida"
        $Shortcut.Save()
        Write-Host "[OK] Atalho criado: $ShortcutPath" -ForegroundColor Green
    } catch {
        Write-Host "[AVISO] Não foi possível criar o atalho na Área de Trabalho: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------
# Etapa 6 - Finalização e abertura do sistema
# ---------------------------------------------------------
Write-Host "[6/6] Finalizando instalação..." -ForegroundColor Cyan
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "   Sistema Casa Vida instalado e pronto!" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""

if (-not $NaoIniciar) {
    $IniciarBat = Join-Path $ProjectRoot "iniciar.bat"
    if (Test-Path -LiteralPath $IniciarBat) {
        Write-Host "[OK] Iniciando o Sistema Casa Vida..." -ForegroundColor Green
        Start-Process -FilePath $IniciarBat -WorkingDirectory $ProjectRoot -WindowStyle Minimized
    } else {
        Write-Host "[AVISO] Arquivo iniciar.bat não encontrado em $ProjectRoot." -ForegroundColor Yellow
    }
    if (-not $NaoPausar) {
        Start-Sleep -Seconds 2
    }
} elseif (-not $NaoPausar) {
    Read-Host "Pressione ENTER para fechar esta janela" | Out-Null
}

exit 0
