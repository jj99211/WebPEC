@echo off
rem Instala WebPEC en este ordenador: comprueba Python, crea el icono del escritorio,
rem prepara los datos (tambien los de una version anterior) y arranca la aplicacion.
rem Se puede repetir sin riesgo, por ejemplo despues de mover la carpeta.
cd /d "%~dp0"
call WebPEC.bat --instalar
