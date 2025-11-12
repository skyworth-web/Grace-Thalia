@echo off
echo ========================================
echo Interview Co-Pilot Plus - Setup Script
echo ========================================
echo.

echo [1/4] Setting up backend...
cd server
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)
cd ..

echo.
echo [2/4] Setting up frontend...
cd client
echo Installing Node.js dependencies...
call npm install
if errorlevel 1 (
    echo ERROR: Failed to install Node.js dependencies
    pause
    exit /b 1
)
cd ..

echo.
echo [3/4] Building extension...
cd client
call npm run build
if errorlevel 1 (
    echo ERROR: Failed to build extension
    pause
    exit /b 1
)
cd ..

echo.
echo [4/4] Creating data directory...
if not exist server\data (
    mkdir server\data
)
if not exist server\data\chroma (
    mkdir server\data\chroma
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Create icon files in client\src\icons\ (see client\src\icons\README.md)
echo 2. Rebuild extension: cd client ^&^& npm run build
echo 3. Start server: cd server ^&^& python main.py
echo 4. Load extension in Chrome from client\dist folder
echo.
pause

