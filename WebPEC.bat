@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title WebPEC
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 webpec.py %*
    goto fin
)
where python >nul 2>nul
if %errorlevel%==0 (
    python webpec.py %*
    goto fin
)
echo.
echo  No se encuentra Python en este ordenador.
echo  Instalalo desde https://www.python.org marcando "Add Python to PATH".
echo.
:fin
pause
