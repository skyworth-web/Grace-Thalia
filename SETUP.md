# Quick Setup Guide

## Prerequisites Check

Before starting, ensure you have:
- ✅ Node.js 18+ installed (`node --version`)
- ✅ Python 3.10+ installed (`python --version`)
- ✅ OpenAI API key (get one at https://platform.openai.com/api-keys)

## Step-by-Step Setup

### 1. Backend Setup

```bash
# Navigate to server directory
cd server

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Set API key as environment variable
# On Windows:
set OPENAI_API_KEY=sk-your-key-here
# On Mac/Linux:
export OPENAI_API_KEY=sk-your-key-here

# Start the server
python main.py
```

The server should now be running on `http://localhost:8000`

### 2. Frontend Setup

Open a **new terminal** (keep the server running):

```bash
# Navigate to client directory
cd client

# Install dependencies
npm install

# Build the extension
npm run build
```

### 3. Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `client/dist` folder (or `dist` folder if you're in the client directory)
5. The extension should now appear in your extensions list

### 4. Create Extension Icons (Required)

The extension needs icon files. Create or download three icon files:
- `client/src/icons/icon16.png` (16x16 pixels)
- `client/src/icons/icon48.png` (48x48 pixels)  
- `client/src/icons/icon128.png` (128x128 pixels)

You can:
- Use any image editor to create simple icons
- Use an online icon generator
- Use placeholder images for testing

After creating icons, rebuild:
```bash
cd client
npm run build
```

Then reload the extension in Chrome (click the refresh icon on the extension card).

### 5. First Use

1. Click the extension icon in Chrome
2. Enter your OpenAI API key
3. Fill in your profile information (optional)
4. Upload your resume (PDF, DOCX, or TXT)
5. Paste the job description
6. Click **Save & Embed** (wait for success message)
7. Click **Start Interview Co-Pilot**
8. Join a meeting on Google Meet, Zoom, or Teams
9. Enable captions/transcripts in the meeting
10. Watch for suggestions in the bottom-right corner!

## Troubleshooting

### "Failed to connect to server"
- Make sure the backend server is running on port 8000
- Check that no firewall is blocking localhost connections
- Try accessing `http://localhost:8000/health` in your browser

### "Cannot find module" errors
- Run `npm install` in the client directory
- Make sure you're using Node.js 18+

### Extension not capturing captions
- Ensure captions are enabled in your meeting platform
- Check browser console (F12) for errors
- Make sure you're on a supported platform (Google Meet, Zoom, Teams)

### Vector store errors
- Delete `server/data/chroma/` folder and try again
- Make sure you've clicked "Save & Embed" after uploading documents

## Development Mode

For development with hot reload:

```bash
# Terminal 1: Backend
cd server
python main.py

# Terminal 2: Frontend (watch mode)
cd client
npm run dev
```

Note: For extension development, you'll need to rebuild and reload the extension after changes.

