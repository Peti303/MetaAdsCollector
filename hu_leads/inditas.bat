@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Kontaktgyujtes indul. Ez 1-2 ora is lehet. Ne zard be az ablakot, a gep ne aludjon el.
if not exist .venv (
  py -m venv .venv || python -m venv .venv
)
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -e .. openpyxl
.venv\Scripts\python.exe gyujto.py
echo.
echo Kesz. Az Excel (kontaktok_....xlsx) ebben a mappaban van. Hiba eseten kuldd el a naplo.txt fajlt.
pause
