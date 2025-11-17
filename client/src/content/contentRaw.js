// Plain content script – NO imports, NO bundler tricks.
// Builds the overlay and handles captions + AI answer.

(function () {
    console.log("[CoPilot] content script loaded");
  
    // ---------- Overlay UI ----------
  
    function createOverlay() {
      if (document.getElementById("interview-copilot-overlay")) return;
  
      var container = document.createElement("div");
      container.id = "interview-copilot-overlay";
  
      Object.assign(container.style, {
        position: "fixed",
        bottom: "20px",
        right: "20px",
        width: "380px",
        height: "420px",
        background: "rgba(15, 15, 15, 0.85)",
        color: "white",
        borderRadius: "14px",
        padding: "16px",
        fontFamily: "Inter, -apple-system, system-ui, sans-serif",
        zIndex: "2147483647",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        display: "flex",
        flexDirection: "column",
      });
  
      container.innerHTML = [
        '<div style="display:flex;justify-content:space-between;align-items:center;">',
        '  <strong style="font-size:14px;opacity:0.9;">🧠 Interview Co-Pilot</strong>',
        '  <button id="copilot-close-btn" style="background:transparent;border:none;color:white;font-size:20px;cursor:pointer;opacity:0.6;">×</button>',
        "</div>",
        '<div id="copilot-transcript" style="flex:1;overflow-y:auto;margin-top:10px;padding-right:6px;font-size:13px;white-space:pre-wrap;">',
        "  Listening for captions...",
        "</div>",
        '<div style="display:flex;margin-top:10px;gap:8px;">',
        '  <button id="copilot-clear-btn" style="flex:1;background:#ff6b6b;border:none;border-radius:8px;padding:10px;color:white;font-weight:600;cursor:pointer;">Clear</button>',
        '  <button id="copilot-generate-btn" style="flex:1;background:#4caf50;border:none;border-radius:8px;padding:10px;color:white;font-weight:600;cursor:pointer;">Generate</button>',
        "</div>",
        '<div id="copilot-answer" style="margin-top:12px;background:rgba(255,255,255,0.08);padding:10px;border-radius:8px;font-size:13px;white-space:pre-wrap;display:none;"></div>',
      ].join("");
  
      document.body.appendChild(container);
  
      var transcriptDiv = container.querySelector("#copilot-transcript");
      var answerDiv = container.querySelector("#copilot-answer");
      var clearBtn = container.querySelector("#copilot-clear-btn");
      var generateBtn = container.querySelector("#copilot-generate-btn");
      var closeBtn = container.querySelector("#copilot-close-btn");
  
      var transcriptText = "";
  
      function updateTranscript(text) {
        transcriptText = (transcriptText + " " + text).trim();
        if (!transcriptText) {
          transcriptDiv.textContent = "Listening for captions...";
        } else {
          if (transcriptText.length > 6000) {
            transcriptText = transcriptText.slice(transcriptText.length - 6000);
          }
          transcriptDiv.textContent = transcriptText;
        }
      }
  
      function showAnswer(text) {
        answerDiv.style.display = "block";
        answerDiv.textContent = text;
      }
  
      // Expose helpers so we can call them later
      window.__copilotUpdateTranscript = updateTranscript;
      window.__copilotShowAnswer = showAnswer;
  
      clearBtn.onclick = function () {
        transcriptText = "";
        transcriptDiv.textContent = "Listening for captions...";
        answerDiv.textContent = "";
        answerDiv.style.display = "none";
      };
  
      generateBtn.onclick = function () {
        var trimmed = (transcriptText || "").trim();
        if (!trimmed) return;
  
        showAnswer("⏳ Generating answer...");
  
        fetch("http://localhost:8000/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ transcript: trimmed }),
        })
          .then(function (res) {
            return res.json();
          })
          .then(function (data) {
            showAnswer(data.answer || "⚠️ No answer generated.");
          })
          .catch(function (err) {
            console.error("[CoPilot] generate error", err);
            showAnswer("❌ Server error while generating answer.");
          });
      };
  
      closeBtn.onclick = function () {
        container.style.display = "none";
      };
    }
  
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", createOverlay);
    } else {
      createOverlay();
    }
  
    // ---------- Caption capture ----------
  
    var lastCaption = "";
    var captionBuffer = "";
    var captionTimeout = null;
  
    function extractGoogleMeetCaptions() {
      var live = document.querySelectorAll("[data-requested-caption]");
      if (live.length > 0) {
        return Array.from(live)
          .map(function (el) {
            return (el.textContent || "").trim();
          })
          .join(" ");
      }
  
      var items = document.querySelectorAll(
        "[data-speaker-id], [data-speaker-text]"
      );
      return Array.from(items)
        .map(function (el) {
          return (el.textContent || "").trim();
        })
        .join(" ");
    }
  
    function extractZoomCaptions() {
      var items = document.querySelectorAll(
        ".transcript-view-lines__line, .transcript-view-line, .zmu-transcript-line"
      );
      return Array.from(items)
        .map(function (el) {
          return (el.textContent || "").trim();
        })
        .filter(Boolean)
        .join(" ");
    }
  
    function extractTeamsCaptions() {
      var items = document.querySelectorAll(
        '[data-tid="closed-caption-text"], .caption-text, .ui-chat__message__content'
      );
      return Array.from(items)
        .map(function (el) {
          return (el.textContent || "").trim();
        })
        .filter(Boolean)
        .join(" ");
    }
  
    function captureCaptions() {
      var url = window.location.href;
      var currentCaption = "";
  
      if (url.indexOf("meet.google.com") !== -1) {
        currentCaption = extractGoogleMeetCaptions();
      } else if (url.indexOf("zoom.us") !== -1) {
        currentCaption = extractZoomCaptions();
      } else if (url.indexOf("teams.microsoft.com") !== -1) {
        currentCaption = extractTeamsCaptions();
      }
  
      if (!currentCaption || currentCaption.length < 10) return;
      if (currentCaption === lastCaption) return;
      lastCaption = currentCaption;
  
      captionBuffer += " " + currentCaption;
  
      if (captionTimeout !== null) {
        clearTimeout(captionTimeout);
      }
  
      captionTimeout = setTimeout(function () {
        var cleaned = captionBuffer.trim();
        captionBuffer = "";
        if (!cleaned) return;
  
        // send to background
        try {
          chrome.runtime.sendMessage({ type: "caption", text: cleaned });
        } catch (e) {
          console.warn("[CoPilot] chrome.runtime not available?", e);
        }
  
        // also update local overlay
        try {
          if (window.__copilotUpdateTranscript) {
            window.__copilotUpdateTranscript(cleaned);
          }
        } catch (e2) {
          console.warn("[CoPilot] updateTranscript failed", e2);
        }
      }, 1500);
    }
  
    var observer = new MutationObserver(function () {
      captureCaptions();
    });
  
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  
    setInterval(captureCaptions, 1000);
  
    // ---------- Receive AI suggestions from backend (via background) ----------
  
    chrome.runtime.onMessage.addListener(function (message) {
      if (message.type === "suggestion") {
        try {
          var prev = window.__copilot_stream_buffer || "";
          var next = prev + (message.text || "");
          window.__copilot_stream_buffer = next;
  
          if (window.__copilotShowAnswer) {
            window.__copilotShowAnswer(next);
          }
        } catch (e) {
          console.warn("[CoPilot] failed to show suggestion", e);
        }
      }
    });
  })();
  