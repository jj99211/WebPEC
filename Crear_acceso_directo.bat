@echo off
rem Crea en el escritorio el icono de WebPEC (con el escudo del instituto)
cd /d "%~dp0"
call WebPEC.bat --crear-acceso-directo
