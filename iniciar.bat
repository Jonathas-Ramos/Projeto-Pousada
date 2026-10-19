@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto erro
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
set COLONIA_SELF_REGISTER=1
echo.
echo Abra http://127.0.0.1:8000 no navegador.
echo Para encerrar, pressione Ctrl+C nesta janela.
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
goto fim
:erro
echo Nao foi possivel iniciar. Confira a mensagem acima e o README.
pause
:fim
endlocal
