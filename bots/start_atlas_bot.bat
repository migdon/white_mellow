@echo off
REM Starts atlas_bot.py and starts it again if it ever stops. Keep this file next to atlas_bot.py.
cd /d "%~dp0"
:loop
echo %date% %time% starting atlas_bot.py
python atlas_bot.py
echo %date% %time% atlas_bot.py stopped - restarting in 60 seconds (close this window to stop for good)
timeout /t 60 /nobreak
goto loop
