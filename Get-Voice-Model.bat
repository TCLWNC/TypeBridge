@echo off
chcp 65001 >nul
title TypeBridge - download the offline speech model
setlocal

rem 语音输入的模型约 228 MB，不进安装包，第一次用之前跑一次这个脚本即可。
rem SenseVoice-Small（Apache-2.0）：中文/英文/日文/韩文/粤语，CPU 上比实时快约 8 倍。

set DIR=%APPDATA%\CrossLink\asr\sense-voice
set BASE=https://hf-mirror.com/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main

echo.
echo 下载到: %DIR%
echo.
if not exist "%DIR%" mkdir "%DIR%"

if exist "%DIR%\model.int8.onnx" if exist "%DIR%\tokens.txt" (
  echo 模型已经在，不用重复下载。
  echo.
  pause
  exit /b 0
)

echo [1/2] model.int8.onnx  ^(约 228 MB，请耐心等^)
curl.exe -L --retry 3 -o "%DIR%\model.int8.onnx" "%BASE%/model.int8.onnx"
if errorlevel 1 (
  echo.
  echo 下载失败。可以手动下载这两个文件放进上面的目录：
  echo   %BASE%/model.int8.onnx
  echo   %BASE%/tokens.txt
  echo.
  pause
  exit /b 1
)

echo [2/2] tokens.txt
curl.exe -L --retry 3 -o "%DIR%\tokens.txt" "%BASE%/tokens.txt"

echo.
echo 完成。回到 TypeBridge 点右上角的「语音输入」就能用了。
echo.
pause
