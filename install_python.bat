@echo off
cd /d "%~dp0"

echo ================================
echo  Step 1 - Install Python 3.11
echo ================================

set PYENV_HOME=%~dp0pyenv-win
set PATH=%PYENV_HOME%\bin;%PYENV_HOME%\shims;%PATH%

if not exist "%PYENV_HOME%" (
    echo Downloading pyenv-win...
    powershell -Command "Invoke-WebRequest -Uri https://github.com/pyenv-win/pyenv-win/archive/master.zip -OutFile pyenv-win.zip"
    if errorlevel 1 ( echo ERROR: Failed to download pyenv-win. Check internet. & pause & exit /b 1 )
    powershell -Command "Expand-Archive -Path pyenv-win.zip -DestinationPath ."
    move pyenv-win-master\pyenv-win "%PYENV_HOME%" >nul
    del pyenv-win.zip
    rmdir /s /q pyenv-win-master
    echo pyenv-win ready.
) else (
    echo pyenv-win already exists, skipping.
)

if not exist "%PYENV_HOME%\versions\3.11.9\python.exe" (
    echo Installing Python 3.11.9...
    pyenv install 3.11.9
    if errorlevel 1 ( echo ERROR: Failed to install Python 3.11.9. & pause & exit /b 1 )
) else (
    echo Python 3.11.9 already installed, skipping.
)

echo.
echo ================================
echo  Python 3.11 ready!
echo  Now run install_packages.bat
echo ================================
pause
