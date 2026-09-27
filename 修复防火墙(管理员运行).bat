@echo off
chcp 65001 >nul
title 修复 CrossLink 防火墙（放行端口段，不绑程序路径）
net session >nul 2>nul
if errorlevel 1 (
  echo 正在申请管理员权限，请在弹出的窗口点「是」…
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

rem 端口段：程序被占用时会自动往后找端口（8788 → 8789 …）
set PORTS=8788-8799

echo.
echo [1/3] 删除旧规则（旧规则绑的是已经不存在的程序路径，所以之前手机搜不到）
netsh advfirewall firewall delete rule name="CrossLink 跨屏输入" >nul 2>nul

echo [2/3] 放行入站 TCP %PORTS%（不限定程序，防止 exe 换路径后失效）
netsh advfirewall firewall add rule name="CrossLink 跨屏输入 TCP" dir=in action=allow protocol=TCP localport=%PORTS% profile=any

echo [3/3] 放行入站 UDP %PORTS%（设备发现靠 UDP 广播）
netsh advfirewall firewall add rule name="CrossLink 跨屏输入 UDP" dir=in action=allow protocol=UDP localport=%PORTS% profile=any

echo.
echo 当前规则：
netsh advfirewall firewall show rule name="CrossLink 跨屏输入 TCP" | findstr /C:"规则名称" /C:"Rule Name" /C:"本地端口" /C:"LocalPort" /C:"协议" /C:"Protocol" /C:"已启用" /C:"Enabled"
netsh advfirewall firewall show rule name="CrossLink 跨屏输入 UDP" | findstr /C:"规则名称" /C:"Rule Name" /C:"本地端口" /C:"LocalPort" /C:"协议" /C:"Protocol" /C:"已启用" /C:"Enabled"

echo.
echo 完成。现在手机重新打开 App，等 3~5 秒应该就能搜到电脑了。
echo （如果仍然搜不到，说明是路由器隔离了设备，不是防火墙。）
echo.
pause
