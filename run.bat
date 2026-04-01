@echo off
set PYTHONUTF8=1
echo [Backend] Iniciando Servidor...
python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
