<#
.SYNOPSIS
    Script simples para sincronizar alterações com o git (Add, Commit, Push).

.DESCRIPTION
    Este script executa:
    1. git pull (para garantir que está atualizado)
    2. git add . (adiciona tudo)
    3. git commit -m "Mensagem" (comita com a mensagem fornecida)
    4. git push (envia para a branch atual)

.PARAMETER Message
    A mensagem de commit. Obrigatória.

.EXAMPLE
    .\sync_git.ps1 "Corrigindo bug na tela de login"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

Write-Host "🔄 Iniciando sincronização Git..." -ForegroundColor Cyan

# 1. Pull
Write-Host "⬇️  Baixando atualizações (Pull)..." -ForegroundColor Yellow
git pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erro ao fazer pull. Resolva os conflitos antes de continuar." -ForegroundColor Red
    exit
}

# 2. Add
Write-Host "➕ Adicionando arquivos (Add)..." -ForegroundColor Yellow
git add .

# 3. Commit
Write-Host "💾 Commitando alterações..." -ForegroundColor Yellow
git commit -m "$Message"

# 4. Push
Write-Host "fg  Enviando para o remoto (Push)..." -ForegroundColor Yellow
git push

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Sincronização concluída com sucesso!" -ForegroundColor Green
} else {
    Write-Host "❌ Erro ao fazer push." -ForegroundColor Red
}
