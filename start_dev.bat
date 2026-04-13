@echo off
set PYTHONUTF8=1
title ROBO RUNNER - Backend + Cloudflare (Dev PC)
echo ========================================
echo   ROBO RUNNER - Iniciando Sistema...
echo   PC: Bruno Dev (D:\Workspace\Tust-AETE)
echo ========================================

cd /d D:\Workspace\Tust-AETE

echo.
echo [1/3] Atualizando codigo (git pull)...
git pull
echo.

echo [2/3] Iniciando Cloudflare Tunnel em segundo plano...
start "CLOUDFLARE TUNNEL" .\cloudflared.exe tunnel run
timeout /t 3 /nobreak > nul

echo [3/3] Iniciando Backend Python...
echo.
set PYTHONUTF8=1
python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
