@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 把 CrossLink 推送到你的仓库

if "%~1"=="" (
  echo.
  echo 用法：先在这个文件夹里打开命令行，然后把仓库地址接在后面，例如：
  echo.
  echo    推送到仓库.bat https://github.com/你的用户名/CrossLink.git
  echo.
  echo 仓库要先在 GitHub / Gitee 上建好，记得新建成"空仓库"（不要勾 README）。
  echo.
  pause
  exit /b 1
)

echo.
echo [1/3] 设置远程地址 origin = %~1
git remote remove origin >nul 2>nul
git remote add origin %~1
if errorlevel 1 (
  echo 设置远程地址失败，检查一下地址写得对不对。
  pause
  exit /b 1
)

echo [2/3] 确认分支是 main
git branch -M main

echo [3/3] 开始推送（第一次会让你填用户名和访问令牌，密码处粘令牌）
git push -u origin main
if errorlevel 1 (
  echo.
  echo 推送失败。常见原因：
  echo   1. 仓库不是空的（在线建仓库时勾了 README）—— 先把远程那个 README 删掉再推
  echo   2. 令牌没勾 repo 权限，或者粘错位置
  echo   3. 网络连不上 GitHub —— 换 Gitee 试
  echo.
  pause
  exit /b 1
)

echo.
echo 推送完成。打开你的仓库页面看看是不是都在了。
pause
