@echo off
cd /d "%~dp0"
echo Starting print server (port 8181)...
start "passnote-print-server" /min python print_server.py
timeout /t 2 >nul
echo Launching browser...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="%~dp0_chrome_print_profile" "http://localhost:8181/live/home.html"
echo Done. You can close this window.
