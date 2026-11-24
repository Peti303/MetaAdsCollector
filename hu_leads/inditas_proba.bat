@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Probafutas indul. Ez kb. 3-5 perc. Ne zard be az ablakot.
if not exist .venv (
  py -m venv .venv || python -m venv .venv
)
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -e ..
.venv\Scripts\python.exe proba.py
echo.
echo Kesz. A proba_eredmeny.txt fajl tartalmat masold be a Claude-nak.
pause
