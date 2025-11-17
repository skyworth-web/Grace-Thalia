let ws: WebSocket | null = null;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "startSession") {
    if (ws) {
      ws.close();
      ws = null;
    }

    ws = new WebSocket("ws://localhost:8000/stream");

    ws.onopen = () => {
      sendResponse({ success: true });
    };

    ws.onerror = () => {
      sendResponse({ success: false, message: "WebSocket error" });
    };

    ws.onmessage = (event) => {
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach((tab) => {
          if (tab.id) {
            chrome.tabs.sendMessage(tab.id, {
              type: "suggestion",
              text: event.data
            }).catch(() => {});
          }
        });
      });
    };

    return true; // async response
  }

  if (msg.type === "caption" && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "caption", text: msg.text }));
    sendResponse({ success: true });
  }
});
