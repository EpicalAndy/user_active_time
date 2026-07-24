@echo off
rem Запуск приложения из venv проекта (.venv) — фиксированный интерпретатор
rem со своими зависимостями (см. requirements.txt). Если .venv нет — создать:
rem   py -3.12 -m venv .venv
rem   .venv\Scripts\python -m pip install -r requirements.txt
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py
