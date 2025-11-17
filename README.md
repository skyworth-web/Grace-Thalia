# Interview Co-Pilot Plus 🧠

A Chrome extension that turns GPT-4o into a real-time interview assistant. It captures live meeting captions, uses your uploaded resume and job description as vector context, and streams concise, personalized answer suggestions during interviews—privately, from your own local environment.

## Features

- 🎯 **Real-time Assistance**: Captures live captions from Google Meet, Zoom, and Microsoft Teams
- 📄 **Resume & Job Context**: Upload your resume and job description for personalized suggestions
- 🤖 **GPT-4o Powered**: Uses OpenAI's GPT-4o-mini for intelligent answer generation
- 🔒 **Private & Local**: Everything runs on your local machine—no data leaves your environment
- 💬 **Streaming Suggestions**: Get real-time answer suggestions as the interview progresses

## Architecture

- **Frontend**: Chrome Extension (React + TypeScript + Vite)
- **Backend**: FastAPI + LangChain + ChromaDB
- **AI Model**: GPT-4o-mini with text-embedding-3-small for vector embeddings

## Setup

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- OpenAI API key
- Chrome browser

### Backend Setup

1. Navigate to the server directory:
```bash
cd server
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set your OpenAI API key (required - must be set in server environment):
```bash
export OPENAI_API_KEY="sk-your-key-here"  # On Windows: set OPENAI_API_KEY=sk-your-key-here
```

5. Start the FastAPI server:
```bash
python main.py
```

The server will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to the client directory:
```bash
cd client
```

2. Install dependencies:
```bash
npm install
```

3. Build the extension:
```bash
npm run build
```

This will create a `dist` folder with the compiled extension.

4. Load the extension in Chrome:
   - Open Chrome and go to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top right)
   - Click "Load unpacked"
   - Select the `dist` folder (or `client/dist` if building from root)

## Usage

1. **Setup**:
   - Make sure the backend server is running with OPENAI_API_KEY set
   - Click the extension icon
   - Upload your resume (PDF, DOCX, or TXT)
   - Optionally paste the job description
   - Click "Save & Embed" to process your documents

2. **Start Interview**:
   - Click "Start Interview Co-Pilot"
   - Join a meeting on Google Meet, Zoom, or Microsoft Teams
   - Enable captions/transcripts in your meeting platform
   - The extension will automatically capture captions and display answer suggestions

3. **View Suggestions**:
   - Suggestions appear in a floating overlay in the bottom-right corner
   - Suggestions are personalized based on your resume and the job description
   - The overlay auto-hides after 30 seconds of inactivity

## Supported Platforms

- ✅ Google Meet
- ✅ Zoom
- ✅ Microsoft Teams

## Project Structure

```
A_Grace/
├── client/                 # Chrome extension
│   ├── src/
│   │   ├── background/     # Background service worker
│   │   ├── content/        # Content scripts for meeting platforms
│   │   ├── popup/          # Extension popup UI
│   │   └── components/     # React components
│   └── package.json
├── server/                 # FastAPI backend
│   ├── chains/            # LangChain chains
│   ├── data/              # Vector store and uploaded files
│   ├── main.py            # FastAPI application
│   └── requirements.txt
└── README.md
```

## Development

### Backend Development

The server uses FastAPI with WebSocket support for real-time streaming. Key endpoints:

- `POST /ingest` - Upload and process resume/job description
- `WS /stream` - WebSocket endpoint for streaming suggestions
- `GET /health` - Health check

### Frontend Development

The extension is built with:
- React 18 for UI components
- TypeScript for type safety
- Vite for fast builds
- Chrome Extension Manifest V3

### Building Icons

You'll need to create icon files for the extension:
- `client/src/icons/icon16.png` (16x16)
- `client/src/icons/icon48.png` (48x48)
- `client/src/icons/icon128.png` (128x128)

You can use any image editor or online icon generator. The icons should represent an interview/assistant theme.

## Troubleshooting

### Extension not capturing captions
- Ensure captions/transcripts are enabled in your meeting platform
- Check that you're on a supported platform (Google Meet, Zoom, Teams)
- Open browser console (F12) to check for errors

### Backend connection errors
- Verify the server is running on port 8000
- Check firewall settings
- Ensure CORS is properly configured (already set for development)

### API key issues
- Verify your OpenAI API key is valid
- Check that you have credits in your OpenAI account
- Ensure the API key is set either via environment variable or in the extension popup

### Vector store errors
- Make sure you've clicked "Save & Embed" after uploading documents
- Check that `server/data/` directory exists and is writable
- Try deleting `server/data/chroma/` and re-embedding

## Privacy & Security

- All processing happens locally on your machine
- Your resume and job description are stored locally in `server/data/`
- API calls are made directly to OpenAI from your machine
- No data is sent to third-party servers (except OpenAI API)

## License

This project is provided as-is for personal use.

## Contributing

Feel free to submit issues and enhancement requests!

