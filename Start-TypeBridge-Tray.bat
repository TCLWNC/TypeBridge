@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem TypeBridge - cross-screen input (跨屏输入)
rem Starts hidden in the tray. Use this one for "run at login".
rem To show the window later: right-click the tray icon -> Show window.
start "" "%~dp0pc\TypeBridge-PC-win64\TypeBridge-PC.exe" --tray
exit
