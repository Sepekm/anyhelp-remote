@echo off
REM Build a standalone AnyHelp.exe (no Python needed on the other PC).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
  --name AnyHelp ^
  --onefile ^
  --windowed ^
  --collect-all aiortc ^
  --collect-all av ^
  --collect-all aioice ^
  --collect-all pygame ^
  --collect-submodules pynput ^
  --collect-all mss ^
  anyhelp.py
echo.
echo Done. The exe is in the "dist" folder: dist\AnyHelp.exe
pause
