@echo off
setlocal
cd /d "%~dp0"

if exist "runtime\node" (
    for /d %%D in (runtime\node\node-v*) do set "NODE_HOME=%%D"
)
if exist "runtime\git\cmd" set "GIT_HOME=runtime\git\cmd"

if defined NODE_HOME set "PATH=%NODE_HOME%;%PATH%"
if defined GIT_HOME set "PATH=%GIT_HOME%;%PATH%"
if exist "%APPDATA%\npm" set "PATH=%APPDATA%\npm;%PATH%"

start "" cmd /c "mimo web"
