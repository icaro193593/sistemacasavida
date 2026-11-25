param(
    [string]$TaskName = "SistemaCasaVida_BackupSemanal"
)

$ErrorActionPreference = "Stop"

$TarefaExistente = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($null -eq $TarefaExistente) {
    Write-Host "A tarefa agendada '$TaskName' não está registrada neste sistema." -ForegroundColor Yellow
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Tarefa agendada '$TaskName' removida com sucesso." -ForegroundColor Green
