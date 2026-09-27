@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 托盘常驻：开机/后台用它。窗口是先藏起来的，
rem 想看界面就右键任务栏右下角的 CrossLink 图标 →「显示窗口」，
rem 出来的是程序自己的窗口（不是甩给浏览器）。
start "" "%~dp0CrossLink-PC-win64\CrossLink-PC.exe" --tray
exit
