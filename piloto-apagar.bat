@echo off
REM Apagar el piloto de PeakStroke (doble clic). Ver docs/PILOTO.md.
title Apagar el piloto
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0piloto.ps1" apagar
echo.
pause
