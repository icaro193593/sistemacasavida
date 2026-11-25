param(
    [string]$TaskName = "SistemaCasaVida_BackupSemanal",
    [ValidateSet("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")]
    [string]$DiaSemana = "Monday",
    [string]$Horario = "09:00"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPythonw = Join-Path $ProjectRoot "venv\Scripts\pythonw.exe"
$ScriptPath = Join-Path $ProjectRoot "scripts\backup_semanal.py"

if (Test-Path -LiteralPath $VenvPythonw) {
    $PythonwPath = $VenvPythonw
} else {
    $CmdPythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($null -ne $CmdPythonw) {
        $PythonwPath = $CmdPythonw.Source
    } else {
        Write-Error "Não foi possível localizar pythonw.exe em '$VenvPythonw' nem no PATH do sistema."
        exit 1
    }
}

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    Write-Error "Script de backup não encontrado em: $ScriptPath"
    exit 1
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonwPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek $DiaSemana `
    -At $Horario

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Backup automático semanal do Sistema Casa Vida com envio por e-mail" `
    -Force | Out-Null

Write-Host ""
Write-Host "Tarefa agendada registrada com sucesso!" -ForegroundColor Green
Write-Host "  Nome       : $TaskName"
Write-Host "  Frequência : Semanal ($DiaSemana às $Horario)"
Write-Host "  Executável : $PythonwPath"
Write-Host "  Script     : $ScriptPath"
Write-Host "  Diretório  : $ProjectRoot"
Write-Host "  Usuário    : $env:USERNAME (sem necessidade de Administrador)"
Write-Host ""
