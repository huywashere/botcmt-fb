@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="%~dp0user_data" --no-first-run --no-default-browser-check "https://www.facebook.com"
exit
