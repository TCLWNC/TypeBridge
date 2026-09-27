@echo off
chcp 65001 >nul
title CrossLink 防火墙放行
net session >nul 2>nul
if errorlevel 1 (
  echo 正在申请管理员权限…
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
rem 放行一个端口段：端口被占用时程序会自动往后找（8788 → 8789 …），
rem 只放行单个端口会导致换端口后就搜不到了。
rem 另外：规则不绑定程序路径。以前绑了 exe 路径，程序一换目录这条规则就形同虚设。
set PORTS=8788-8800
echo.
echo 给 CrossLink 放行入站端口 %PORTS% (TCP + UDP) …
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入" >nul 2>nul
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入 TCP" >nul 2>nul
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入 UDP" >nul 2>nul
netsh advfirewall firewall add rule name="CrossLink 跨屏输入 TCP" dir=in action=allow protocol=TCP localport=%PORTS% profile=any
netsh advfirewall firewall add rule name="CrossLink 跨屏输入 UDP" dir=in action=allow protocol=UDP localport=%PORTS% profile=any
echo.
echo 当前规则：
netsh advfirewall firewall show rule name="CrossLink 跨屏输入 TCP" | findstr /C:"规则名称" /C:"Rule Name" /C:"本地端口" /C:"LocalPort" /C:"协议" /C:"Protocol" /C:"已启用" /C:"Enabled"
netsh advfirewall firewall show rule name="CrossLink 跨屏输入 UDP" | findstr /C:"规则名称" /C:"Rule Name" /C:"本地端口" /C:"LocalPort" /C:"协议" /C:"Protocol" /C:"已启用" /C:"Enabled"
echo.
echo 完成。手机现在应该能连上了。
echo 想撤销就运行「删除防火墙规则.bat」。
echo.
pause
