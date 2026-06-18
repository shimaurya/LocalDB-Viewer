#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python -m venv .venv
. .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate
pip install -q -r requirements.txt
exec python app.py
