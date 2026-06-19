@echo off
REM Lanzador de PeakStroke: arranca backend + frontend y los apaga todos al cerrar.
title PeakStroke
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0peakstroke-run.ps1"
