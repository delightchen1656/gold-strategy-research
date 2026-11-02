@echo off
cd /d "%~dp0"
"%~dp0runtime\python.exe" "%~dp0run.py" %*
if errorlevel 1 pause
