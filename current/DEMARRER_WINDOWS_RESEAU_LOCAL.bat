@echo off
setlocal
cd /d "%~dp0"
echo Serveur disponible sur le reseau local (port 8765).
echo ATTENTION : ne pas rediriger ce port sur Internet.
echo Tapez ipconfig pour obtenir l'adresse IPv4 de ce PC.
echo.
where py >nul 2>&1
if errorlevel 1 goto :python
py -3 server.py --host 0.0.0.0 --port 8765
goto :end
:python
python server.py --host 0.0.0.0 --port 8765
:end
echo.
echo Serveur arrete. Appuyez sur une touche pour fermer.
pause >nul
