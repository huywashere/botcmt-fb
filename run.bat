@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Facebook Page Auto Commenter
cd /d "%~dp0"
echo ========================================================
echo   Facebook Page Auto Commenter - Pro Edition
echo ========================================================
echo Dang khoi dong ung dung...
python main.py
pause
