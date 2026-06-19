@echo off
set "MIMO_HOME=%~dp0"
if exist "%MIMO_HOME%runtime\node\node-v20.15.1-win-x64" set "PATH=%MIMO_HOME%runtime\node\node-v20.15.1-win-x64;%PATH%"
if exist "%MIMO_HOME%runtime\git\cmd" set "PATH=%MIMO_HOME%runtime\git\cmd;%PATH%"
if exist "%APPDATA%\npm" set "PATH=%APPDATA%\npm;%PATH%"
start "" cmd /c "mimo web"
