@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 把 CrossLink 推送到仓库

rem 这个文件夹已经接好了仓库：https://github.com/TCLWNC/CrossLink
rem 凭据存在 Windows 凭据管理器里，双击直接推，不会再问账号密码。
rem 如果哪天换了仓库，把新地址当参数传进来即可，例如：
rem    推送到仓库.bat https://github.com/你的名字/新仓库.git

if not "%~1"=="" (
  echo 换绑远程地址 origin = %~1
  git remote remove origin >nul 2>nul
  git remote add origin %~1
)

echo [1/3] 检查改动
git add -A
git status --short

echo [2/3] 提交
git commit -m "更新：%DATE% %TIME%" 2>nul
if errorlevel 1 echo （没有需要提交的改动，直接推送）

echo [3/3] 推送到 origin
git branch -M main
git push -u origin main
if errorlevel 1 (
  echo.
  echo 推送失败，常见原因：
  echo   1. 凭据过期或被撤销 —— 重新生成一个访问令牌，再执行一次：
  echo      git credential approve
  echo   2. 网络连不上 GitHub —— 换个网络或代理再试
  echo.
  pause
  exit /b 1
)

echo.
echo 推送完成：https://github.com/TCLWNC/CrossLink
pause
