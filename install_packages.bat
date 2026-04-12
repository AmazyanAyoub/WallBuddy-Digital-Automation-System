@echo off
cd /d "%~dp0"

echo ================================
echo  Step 2 - Install Packages
echo ================================

set PYENV_HOME=%~dp0pyenv-win
set PYTHON311=%PYENV_HOME%\versions\3.11.9\python.exe
set PYTHON=%~dp0venv\Scripts\python.exe

if not exist "%PYTHON311%" (
    echo ERROR: Python 3.11 not found. Run install_python.bat first.
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo Creating virtual environment...
    "%PYTHON311%" -m venv "%~dp0venv"
    if errorlevel 1 ( echo ERROR: Failed to create venv. & pause & exit /b 1 )
) else (
    echo venv already exists, skipping.
)

echo Upgrading pip...
"%PYTHON%" -m pip install --quiet --upgrade pip

echo Pinning setuptools...
"%PYTHON%" -m pip install --quiet "setuptools==65.5.0" wheel
if errorlevel 1 ( echo ERROR: Failed to install setuptools. & pause & exit /b 1 )

echo Installing PyTorch CPU...
"%PYTHON%" -m pip install --quiet torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo ERROR: Failed to install PyTorch. & pause & exit /b 1 )

echo Installing core dependencies...
"%PYTHON%" -m pip install --quiet pillow opencv-python numpy
if errorlevel 1 ( echo ERROR: Failed to install core dependencies. & pause & exit /b 1 )

echo Installing basicsr...
"%PYTHON%" -m pip install --quiet basicsr --no-build-isolation
if errorlevel 1 ( echo ERROR: Failed to install basicsr. & pause & exit /b 1 )

echo Installing realesrgan...
"%PYTHON%" -m pip install --quiet realesrgan --no-build-isolation
if errorlevel 1 ( echo ERROR: Failed to install realesrgan. & pause & exit /b 1 )

echo Installing Google Drive packages...
"%PYTHON%" -m pip install --quiet google-api-python-client google-auth-oauthlib
if errorlevel 1 ( echo ERROR: Failed to install Google Drive packages. & pause & exit /b 1 )

echo Installing LangChain + OpenAI...
"%PYTHON%" -m pip install --quiet langchain-openai
if errorlevel 1 ( echo ERROR: Failed to install langchain-openai. & pause & exit /b 1 )

echo.
echo ================================
echo  All packages installed!
echo  Run run.bat to start the pipeline.
echo ================================
pause
