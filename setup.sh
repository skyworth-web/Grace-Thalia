#!/bin/bash

echo "========================================"
echo "Interview Co-Pilot Plus - Setup Script"
echo "========================================"
echo ""

echo "[1/4] Setting up backend..."
cd server
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
echo "Activating virtual environment..."
source venv/bin/activate
echo "Installing Python dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies"
    exit 1
fi
cd ..

echo ""
echo "[2/4] Setting up frontend..."
cd client
echo "Installing Node.js dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Node.js dependencies"
    exit 1
fi
cd ..

echo ""
echo "[3/4] Building extension..."
cd client
npm run build
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to build extension"
    exit 1
fi
cd ..

echo ""
echo "[4/4] Creating data directory..."
mkdir -p server/data/chroma

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Create icon files in client/src/icons/ (see client/src/icons/README.md)"
echo "2. Rebuild extension: cd client && npm run build"
echo "3. Start server: cd server && python main.py"
echo "4. Load extension in Chrome from client/dist folder"
echo ""

