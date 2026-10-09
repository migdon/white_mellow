@echo off
REM Runs atlas_bot.py and starts it again if it ever stops. Close this window to stop for good.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% --version >nul 2>nul || (echo Python is not installed: get the 64-bit Python from python.org and tick "Add python.exe to PATH". & pause & exit /b 1)
:loop
echo %date% %time% starting atlas_bot.py
%PY% atlas_bot.py
echo %date% %time% atlas_bot.py stopped - restarting in 60 seconds (close this window to stop for good)
timeout /t 60 /nobreak
goto loop
