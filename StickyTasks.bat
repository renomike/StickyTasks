@echo off
REM Launch StickyTasks without a console window.
REM pythonw is the windowed Python launcher installed alongside python.exe.
cd /d "%~dp0"
start "" pythonw.exe run_stickytasks.py
