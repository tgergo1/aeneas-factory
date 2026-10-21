@echo off
rem Aeneas Factory command line (Windows). Runs the aeneas package in the factory's own environment (.venv).
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo The factory environment is missing. Run: py install.py factory  ^(in %ROOT%^) 1>&2
  exit /b 1
)
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
"%PY%" -m aeneas %*
