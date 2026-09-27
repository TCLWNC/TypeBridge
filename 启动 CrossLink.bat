@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "%~dp0CrossLink-PC-win64\CrossLink-PC.exe"
exit
