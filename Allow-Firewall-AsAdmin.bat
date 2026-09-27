@echo off
chcp 65001 >nul
title TypeBridge - allow firewall (TCP/UDP 8788-8800)
net session >nul 2>nul
if errorlevel 1 (
  echo Asking for administrator rights...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
rem The app walks up the port range when a port is taken (8788 -> 8789 ...),
rem and the rule deliberately does NOT bind an exe path: an old rule bound to a
rem previous build path is exactly why phones could not find the PC before.
set PORTS=8788-8800
echo.
echo Allowing inbound ports %PORTS% (TCP + UDP) for TypeBridge ...
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入" >nul 2>nul
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入 TCP" >nul 2>nul
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入 UDP" >nul 2>nul
netsh advfirewall firewall add rule name="CrossLink 跨屏输入 TCP" dir=in action=allow protocol=TCP localport=%PORTS% profile=any
netsh advfirewall firewall add rule name="CrossLink 跨屏输入 UDP" dir=in action=allow protocol=UDP localport=%PORTS% profile=any
echo.
echo Current rules:
netsh advfirewall firewall show rule name="CrossLink 跨屏输入 TCP" | findstr /C:"Rule Name" /C:"LocalPort" /C:"Protocol" /C:"Enabled"
netsh advfirewall firewall show rule name="CrossLink 跨屏输入 UDP" | findstr /C:"Rule Name" /C:"LocalPort" /C:"Protocol" /C:"Enabled"
echo.
echo Done. Open the phone app again - it should find the PC within a few seconds.
echo (Still nothing? Then the router is isolating clients - not the firewall.)
echo.
pause
