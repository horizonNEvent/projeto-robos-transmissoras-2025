@echo off
REM =================================================================
REM Script de Deploy Automático - TUST Portal (Windows)
REM =================================================================

echo.
echo 🚀 Iniciando deploy da nova versão...
echo.

REM 1. Atualiza o código fonte via Git
echo 📥 Puxando atualizações do repositório...
git fetch origin feature/robot-ui-final
git reset --hard origin/feature/robot-ui-final
if errorlevel 1 (
    echo ❌ Erro ao atualizar repositório!
    exit /b 1
)

REM 2. Para os containers atuais
echo 🛑 Parando containers atuais...
docker-compose down
if errorlevel 1 (
    echo ⚠️ Aviso: erro ao parar containers (talvez não estejam rodando)
)

REM 3. Reconstrói e inicia os containers
echo 🏗️ Construindo imagens e iniciando containers...
docker-compose up -d --build --force-recreate
if errorlevel 1 (
    echo ❌ Erro ao subir containers!
    exit /b 1
)

REM 4. Limpeza de imagens antigas
echo 🧹 Limpando imagens antigas...
docker image prune -f

echo.
echo ✅ Deploy finalizado com sucesso!
echo   - Backend: http://192.168.0.105:8000
echo   - Frontend: http://192.168.0.105:5173
echo.

exit /b 0
