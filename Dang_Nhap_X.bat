@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "CHROME_BIN="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "CHROME_BIN=C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set "CHROME_BIN=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_BIN=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if defined CHROME_BIN (
    start "" "%CHROME_BIN%" --user-data-dir="%~dp0x_user_data" --no-first-run --no-default-browser-check "https://x.com/login"
) else (
    start "" "chrome" --user-data-dir="%~dp0x_user_data" --no-first-run --no-default-browser-check "https://x.com/login"
)
exit
