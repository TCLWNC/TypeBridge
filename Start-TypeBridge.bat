@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem TypeBridge - cross-screen input (跨屏输入)
rem Starts the PC app with its own window.
start "" "%~dp0pc\TypeBridge-PC-win64\TypeBridge-PC.exe"
exit
