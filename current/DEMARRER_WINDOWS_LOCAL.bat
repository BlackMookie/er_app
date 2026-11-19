@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto :python
py -3 server.py --host 127.0.0.1 --port 8765
goto :end
:python
python server.py --host 127.0.0.1 --port 8765
:end
echo.
echo Serveur arrete. Appuyez sur une touche pour fermer.
pause >nul
