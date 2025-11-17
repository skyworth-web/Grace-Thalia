let ws: WebSocket | null = null;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "startSession") {
    // Close existing connection if any
    if (ws) {
      ws.close();
      ws = null;
    }

    try {
      // Connect to backend WebSocket
      ws = new WebSocket("ws://localhost:8000/stream");

      let connectionEstablished = false;

      ws.onopen = () => {
        console.log("✅ Connected to Interview Co-Pilot backend");
        connectionEstablished = true;
        // Send success response if callback is still available
        try {
          sendResponse({ success: true, message: "Connected to backend" });
        } catch (e) {
          // Response already sent or callback expired
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
        if (!connectionEstablished) {
          try {
            sendResponse({ 
              success: false, 
              message: "Failed to connect to backend. Is the server running?" 
            });
          } catch (e) {
            // Response already sent or callback expired
          }
        }
      };

      ws.onclose = (event) => {
        console.log("WebSocket connection closed", event.code, event.reason);
        ws = null;
      };

      // Set a timeout to send response if connection takes too long
      setTimeout(() => {
        if (!connectionEstablished) {
          try {
            sendResponse({ 
              success: false, 
              message: "Connection timeout. Please check if server is running." 
            });
          } catch (e) {
            // Response already sent
          }
        }
      }, 3000);

    } catch (error) {
      console.error("Error creating WebSocket:", error);
      sendResponse({ 
        success: false, 
        message: `Failed to start session: ${error.message || "Unknown error"}` 
      });
    }

    return true; // Keep message channel open for async response
  } else if (msg.type === "caption") {
    // Forward caption text to backend
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "caption", text: msg.text }));
      sendResponse({ success: true });
    } else {
      sendResponse({ success: false, message: "WebSocket not connected" });
    }
    return false; // Synchronous response
  }

  return false; // No async response needed
});

// Cleanup on extension unload
chrome.runtime.onSuspend.addListener(() => {
  if (ws) {
    ws.close();
  }
});
