import React from "react";
import ReactDOM from "react-dom/client";
import Overlay from "../components/Overlay";

// Inject overlay into the page
const container = document.createElement("div");
container.id = "interview-copilot-overlay";
document.body.appendChild(container);

const root = ReactDOM.createRoot(container);
root.render(
  <React.StrictMode>
    <Overlay />
  </React.StrictMode>
);

// Capture captions from various meeting platforms
let lastCaption = "";
let captionBuffer = "";
let captionTimeout: NodeJS.Timeout | null = null;

function extractGoogleMeetCaptions(): string {
  // Google Meet caption selector
  const captionElements = document.querySelectorAll('[data-speaker-id]');
  if (captionElements.length === 0) {
    // Try alternative selector
    const altElements = document.querySelectorAll('[data-speaker-text]');
    if (altElements.length > 0) {
      return Array.from(altElements)
        .map((el) => el.textContent?.trim() || "")
        .join(" ");
    }
    return "";
  }
  return Array.from(captionElements)
    .map((el) => el.textContent?.trim() || "")
    .join(" ");
}

function extractZoomCaptions(): string {
  // Zoom caption selector
  const captionElements = document.querySelectorAll(
    ".transcript-view-lines__line, .transcript-view-line"
  );
  if (captionElements.length === 0) {
    return "";
  }
  return Array.from(captionElements)
    .map((el) => el.textContent?.trim() || "")
    .join(" ");
}

function extractTeamsCaptions(): string {
  // Microsoft Teams caption selector
  const captionElements = document.querySelectorAll(
    '[data-tid="closed-caption-text"], .caption-text'
  );
  if (captionElements.length === 0) {
    return "";
  }
  return Array.from(captionElements)
    .map((el) => el.textContent?.trim() || "")
    .join(" ");
}

function captureCaptions() {
  const url = window.location.href;
  let currentCaption = "";

  if (url.includes("meet.google.com")) {
    currentCaption = extractGoogleMeetCaptions();
  } else if (url.includes("zoom.us")) {
    currentCaption = extractZoomCaptions();
  } else if (url.includes("teams.microsoft.com")) {
    currentCaption = extractTeamsCaptions();
  }

  // Only send if caption has changed and is not empty
  if (currentCaption && currentCaption !== lastCaption && currentCaption.length > 10) {
    lastCaption = currentCaption;
    
    // Buffer captions and send in chunks to avoid overwhelming the backend
    captionBuffer += currentCaption + " ";
    
    if (captionTimeout) {
      clearTimeout(captionTimeout);
    }
    
    captionTimeout = setTimeout(() => {
      if (captionBuffer.trim()) {
        chrome.runtime.sendMessage({
          type: "caption",
          text: captionBuffer.trim(),
        });
        captionBuffer = "";
      }
    }, 2000); // Send every 2 seconds or when buffer accumulates
  }
}

// Start capturing captions
const observer = new MutationObserver(() => {
  captureCaptions();
});

observer.observe(document.body, {
  childList: true,
  subtree: true,
  characterData: true,
});

// Also poll periodically as a fallback
setInterval(captureCaptions, 1000);

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "suggestion") {
    // The overlay component will handle this via its own listener
    window.dispatchEvent(
      new CustomEvent("copilot-suggestion", { detail: message.text })
    );
  }
});
