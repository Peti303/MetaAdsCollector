#!/usr/bin/env bash
# macOS / Linux megfeleloje az inditas_proba.bat-nak
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e ..
.venv/bin/python proba.py
