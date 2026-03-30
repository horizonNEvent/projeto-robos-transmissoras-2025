# =================================================================
# Script de Deploy Automático - TUST Portal (PowerShell Windows)
# =================================================================

Write-Host ""
Write-Host "🚀 Iniciando deploy da nova versão..."
Write-Host ""

# 1. Atualiza o código fonte via Git
Write-Host "📥 Puxando atualizações do repositório..."
git fetch origin feature/robot-ui-final
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erro ao fazer fetch!" -ForegroundColor Red
    exit 1
}

git reset --hard origin/feature/robot-ui-final
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erro ao fazer reset!" -ForegroundColor Red
    exit 1
}

# 2. Para os containers atuais
Write-Host "🛑 Parando containers atuais..."
docker-compose down
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ Aviso: erro ao parar containers (talvez não estejam rodando)" -ForegroundColor Yellow
}

# 3. Reconstrói e inicia os containers
Write-Host "🏗️ Construindo imagens e iniciando containers..."
docker-compose up -d --build --force-recreate
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erro ao subir containers!" -ForegroundColor Red
    exit 1
}

# 4. Limpeza de imagens antigas
Write-Host "🧹 Limpando imagens antigas..."
docker image prune -f

Write-Host ""
Write-Host "✅ Deploy finalizado com sucesso!" -ForegroundColor Green
Write-Host "   - Backend: http://192.168.0.105:8000"
Write-Host "   - Frontend: http://192.168.0.105:5173"
Write-Host ""

exit 0
