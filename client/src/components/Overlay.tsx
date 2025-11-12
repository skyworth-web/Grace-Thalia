import { useEffect, useState } from "react";

export default function Overlay() {
  const [text, setText] = useState("");
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Listen for messages from background script
    const messageListener = (m: any) => {
      if (m.type === "suggestion") {
        setText((prev) => {
          // Append new text, but limit total length
          const newText = prev + m.text;
          return newText.slice(-2000); // Keep last 2000 chars
        });
        setIsVisible(true);
      }
    };

    // Listen for custom events from content script
    const eventListener = (e: CustomEvent) => {
      setText((prev) => {
        const newText = prev + e.detail;
        return newText.slice(-2000);
      });
      setIsVisible(true);
    };

    chrome.runtime.onMessage.addListener(messageListener);
    window.addEventListener("copilot-suggestion", eventListener as EventListener);

    // Auto-hide after 30 seconds of no updates
    const hideTimer = setInterval(() => {
      setIsVisible(false);
    }, 30000);

    return () => {
      chrome.runtime.onMessage.removeListener(messageListener);
      window.removeEventListener("copilot-suggestion", eventListener as EventListener);
      clearInterval(hideTimer);
    };
  }, []);

  if (!isVisible && !text) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "1.5rem",
        right: "1.5rem",
        width: "360px",
        maxHeight: "400px",
        background: "rgba(20, 20, 20, 0.95)",
        color: "white",
        borderRadius: "12px",
        padding: "1rem",
        fontFamily: "Inter, -apple-system, sans-serif",
        zIndex: 2147483647,
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        overflow: "auto",
        transition: "opacity 0.3s ease",
        opacity: isVisible ? 1 : 0.7,
      }}
    >
      <div
        style={{
          fontSize: "0.75rem",
          opacity: 0.7,
          marginBottom: "0.5rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>💬 Co-Pilot Suggestion</span>
        <button
          onClick={() => setIsVisible(false)}
          style={{
            background: "transparent",
            border: "none",
            color: "white",
            cursor: "pointer",
            fontSize: "1.2rem",
            opacity: 0.7,
          }}
        >
          ×
        </button>
      </div>
      <div
        style={{
          whiteSpace: "pre-wrap",
          fontSize: "0.875rem",
          lineHeight: "1.5",
          wordWrap: "break-word",
        }}
      >
        {text || "Listening for interview questions..."}
      </div>
    </div>
  );
}
