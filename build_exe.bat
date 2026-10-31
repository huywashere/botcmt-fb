@echo off
chcp 65001 >nul
title Dong Goi Facebook Page Auto Commenter sang .EXE
cd /d "%~dp0"
echo ========================================================
echo   DONG GOI PHAN MEM SANG FILE .EXE DOC LAP
echo ========================================================
echo Dang cai dat PyInstaller...
python -m pip install pyinstaller
echo Dang dong goi file executable...
python -m PyInstaller --noconfirm --onedir --windowed ^
    --add-data "web;web" ^
    --add-data "core;core" ^
    --name "FacebookAutoCommenter" ^
    main.py
echo ========================================================
echo   HOAN TAT!
echo File .exe da duoc tao trong thu muc: dist\FacebookAutoCommenter\
echo ========================================================
pause
