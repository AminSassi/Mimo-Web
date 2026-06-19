@echo off
title MiMo Auto Pre-Flight Check
color 0B
echo.
echo  ==========================================
echo   MiMo Auto v2.1 - Pre-Flight Check
echo  ==========================================
echo.

echo  [1/7] Operating System
for /f "tokens=2 delims=[]" %%a in ('ver') do set ver=%%a
echo   %ver%

echo.
echo  [2/7] Administrator
net session >nul 2>&1
if %errorlevel%==0 (
    echo   YES - Running as Administrator
) else (
    echo   NO  - Run installer as Administrator!
)

echo.
echo  [3/7] Internet Connection
ping -n 1 -w 1000 8.8.8.8 >nul 2>&1
if %errorlevel%==0 (
    echo   Connected
) else (
    echo   DISCONNECTED - Internet required for installation
)

echo.
echo  [4/7] Disk Space
for /f "tokens=3" %%a in ('dir C:\ ^| findstr /c:"bytes free"') do set free=%%a
echo   C:\ free: %free% bytes

echo.
echo  [5/7] Dependencies
echo   Checking Node.js...
node --version >nul 2>&1
if %errorlevel%==0 (
    for /f %%a in ('node --version') do echo     Node.js: %%a
) else (
    echo     Node.js: NOT FOUND (will be installed)
)

echo   Checking Git...
git --version >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=3" %%a in ('git --version') do echo     Git: %%a
) else (
    echo     Git: NOT FOUND (will be installed)
)

echo   Checking npm...
npm --version >nul 2>&1
if %errorlevel%==0 (
    for /f %%a in ('npm --version') do echo     npm: %%a
) else (
    echo     npm: NOT FOUND (will be installed with Node.js)
)

echo.
echo  [6/7] Python / PyTorch
python --version >nul 2>&1
if %errorlevel%==0 (
    for /f %%a in ('python --version') do echo     %%a
) else (
    echo     Python: NOT FOUND
)

python -c "import torch; print(f'    PyTorch: {torch.__version__}'); print(f'    CUDA: {torch.version.cuda}'); print(f'    cuDNN: {torch.backends.cudnn.version()}')" >nul 2>&1
if %errorlevel%==0 (
    python -c "import torch; print(f'    PyTorch: {torch.__version__}'); print(f'    CUDA: {torch.version.cuda}'); print(f'    cuDNN: {torch.backends.cudnn.version()}')"
) else (
    echo     PyTorch: NOT FOUND or no CUDA support
)

echo.
echo  [7/7] NVIDIA GPU
nvidia-smi --query-gpu=name,driver_version,compute_cap,memory.total --format=csv,noheader >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=name,driver_version,compute_cap,memory.total --format=csv,noheader') do echo     %%a
    nvidia-smi --query-gpu=memory.free --format=csv,noheader >nul 2>&1
    if %errorlevel%==0 (
        for /f %%a in ('nvidia-smi --query-gpu=memory.free --format=csv,noheader') do echo     Free VRAM: %%a MB
    )
) else (
    echo     NVIDIA GPU: NOT DETECTED
    echo     WARNING: MiMo Auto requires an NVIDIA GPU with CUDA support
)

echo.
echo  ==========================================
echo   Pre-flight check complete
echo  ==========================================
echo.
pause
