@echo off
title MiMo Pre-Flight Check
color 0B
echo.
echo  ============================================
echo   MiMo Installer — Pre-Flight Check
echo  ============================================
echo.
echo  This checks if your PC is ready for install.
echo  Takes 5 seconds. No changes are made.
echo.

echo  [1/6] Windows Version...
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
echo         Windows %VERSION%
echo.

echo  [2/6] Administrator Rights...
net session >nul 2>&1
if %errorlevel% == 0 (
    echo         Admin: YES
) else (
    echo         Admin: NO — Right-click this file and "Run as administrator"
)
echo.

echo  [3/6] Internet Connection...
ping -n 1 google.com >nul 2>&1
if %errorlevel% == 0 (
    echo         Internet: CONNECTED
) else (
    echo         Internet: DISCONNECTED — Check your network
)
echo.

echo  [4/7] Disk Space...
for /f "tokens=3" %%a in ('dir C:\ /-c 2^>nul ^| findstr /C:"bytes free"') do set FREE=%%a
echo         Free space on C: %FREE% bytes
echo.

echo  [5/7] NVIDIA GPU...
where nvidia-smi >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2^>nul') do echo         GPU: %%i
) else (
    echo         GPU: NOT DETECTED — NVIDIA GPU with CUDA required
    echo         You need an NVIDIA GPU with 4GB+ VRAM to run MiMo Auto
)
echo.

echo  [6/7] Checking Dependencies...
echo.
where node >nul 2>&1
if %errorlevel% == 0 (
    for /f %%i in ('node --version') do echo         Node.js: %%i
) else (
    echo         Node.js: NOT FOUND — will be installed automatically
)

where npm >nul 2>&1
if %errorlevel% == 0 (
    for /f %%i in ('npm --version') do echo         npm: %%i
) else (
    echo         npm: NOT FOUND — will be installed automatically
)

where git >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=3" %%i in ('git --version') do echo         Git: %%i
) else (
    echo         Git: NOT FOUND — will be installed automatically
)

where python >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo         Python: %%i
) else (
    echo         Python: NOT FOUND — will be installed automatically
)
echo.

echo  [7/7] Checking MiMo...
where mimo >nul 2>&1
if %errorlevel% == 0 (
    echo         MiMo: INSTALLED
) else (
    if exist "%USERPROFILE%\.mimocode\bin\mimo.exe" (
        echo         MiMo: Found in ~/.mimocode/bin/
    ) else (
        echo         MiMo: NOT INSTALLED — will be installed
    )
)

echo.
echo  ============================================
echo   CHECK COMPLETE
echo  ============================================
echo.
echo  If any item says "NOT FOUND", don't worry —
echo  the installer will handle it automatically.
echo.
echo  To install MiMo, run "MiMo Installer.exe"
echo.
pause
