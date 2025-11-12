let ws: WebSocket | null = null;
let apiKey: string = "";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "startSession") {
    apiKey = msg.apiKey;
    
    // Close existing connection if any
    if (ws) {
      ws.close();
    }

    // Connect to backend WebSocket
    ws = new WebSocket("ws://localhost:8000/stream");

    ws.onopen = () => {
      console.log("✅ Connected to Interview Co-Pilot backend");
      // Send API key to backend
      if (apiKey) {
        ws?.send(JSON.stringify({ type: "api_key", key: apiKey }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "suggestion") {
          // Send suggestion to all tabs with the extension
          chrome.tabs.query({}, (tabs) => {
            tabs.forEach((tab) => {
              if (tab.id) {
                chrome.tabs.sendMessage(tab.id, {
                  type: "suggestion",
                  text: data.text,
                }).catch(() => {
                  // Ignore errors for tabs that don't have content script
                });
              }
            });
          });
        } else if (data.type === "error") {
          console.error("Backend error:", data.message);
        }
      } catch (e) {
        // If not JSON, treat as plain text
        chrome.tabs.query({}, (tabs) => {
          tabs.forEach((tab) => {
            if (tab.id) {
              chrome.tabs.sendMessage(tab.id, {
                type: "suggestion",
                text: event.data,
              }).catch(() => {});
            }
          });
        });
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      console.log("WebSocket connection closed");
      ws = null;
    };
  } else if (msg.type === "caption") {
    // Forward caption text to backend
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "caption", text: msg.text }));
    }
  }

  return true; // Keep message channel open for async response
});

// Cleanup on extension unload
chrome.runtime.onSuspend.addListener(() => {
  if (ws) {
    ws.close();
  }
});
