@echo off
REM Levantar el piloto de PeakStroke (doble clic). Ver docs/PILOTO.md.
title Levantar el piloto
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0piloto.ps1" levantar
echo.
pause
