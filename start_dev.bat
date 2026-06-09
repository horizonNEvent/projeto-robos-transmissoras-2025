@echo off
set PYTHONUTF8=1
title ROBO RUNNER - Backend + Cloudflare (Dev PC)
echo ========================================
echo   ROBO RUNNER - Iniciando Sistema...
echo   PC: Bruno Dev (D:\Workspace\Tust-AETE)
echo ========================================

cd /d "%~dp0"

echo.
echo [1/4] Atualizando codigo (git pull)...
git pull

echo.
echo [2/4] Iniciando Backend Python (janela separada)...
start "ROBO RUNNER - Backend" cmd /k "cd /d %~dp0 && set PYTHONUTF8=1 && python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo       Aguardando backend em http://127.0.0.1:8000 (ate 90s)...
set /a _tries=0
:wait_backend
ping -n 2 127.0.0.1 > nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" | findstr /i "True" >nul
if %errorlevel%==0 goto backend_ok
set /a _tries+=1
if %_tries% lss 45 goto wait_backend
echo       ERRO: backend nao respondeu. Veja a janela "ROBO RUNNER - Backend".
echo       Tunnel e deploy Vercel NAO serao iniciados ate o backend subir.
goto done

:backend_ok
echo       Backend OK.
powershell -ExecutionPolicy Bypass -File start_tunnel.ps1
if %errorlevel% neq 0 (
    echo       ERRO: start_tunnel.ps1 falhou.
)

:done

echo.
echo [4/4] Pronto.
echo       Backend: janela "ROBO RUNNER - Backend" (localhost:8000)
echo       Frontend: deploy Vercel em segundo plano (se iniciado)
echo.
pause
