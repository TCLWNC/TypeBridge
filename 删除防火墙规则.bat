@echo off
chcp 65001 >nul
title CrossLink 删除防火墙规则
net session >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入"
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入 TCP"
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入 UDP"
echo.
echo 已删除 CrossLink 的防火墙规则。
pause
