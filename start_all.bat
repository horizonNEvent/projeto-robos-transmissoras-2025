@echo off
set PYTHONUTF8=1
title ROBO RUNNER - Backend + Ngrok
echo ========================================
echo   ROBO RUNNER - Iniciando Sistema...
echo ========================================

cd /d C:\Workspace-lab\projeto-robos-transmissoras-2025

echo.
echo [1/3] Atualizando codigo (git pull)...
git pull
echo.

echo [2/3] Iniciando Ngrok em segundo plano...
start "NGROK TUNNEL" ngrok http 8000
timeout /t 3 /nobreak > nul

echo [3/3] Iniciando Backend Python...
echo.
set PYTHONUTF8=1
python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
