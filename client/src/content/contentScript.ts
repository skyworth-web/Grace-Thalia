// Plain content script – no React, no imports.
// Builds the overlay and handles captions + AI answer.

(() => {
  console.log("[CoPilot] content script injected");

  // ---------- Overlay UI ----------

  function createOverlay() {
    if (document.getElementById("interview-copilot-overlay")) return;

    const container = document.createElement("div");
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

    container.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong style="font-size:14px;opacity:0.9;">🧠 Interview Co-Pilot</strong>
        <button id="copilot-close-btn"
          style="background:transparent;border:none;color:white;font-size:20px;cursor:pointer;opacity:0.6;">
          ×
        </button>
      </div>

      <div id="copilot-transcript"
        style="flex:1;overflow-y:auto;margin-top:10px;padding-right:6px;font-size:13px;white-space:pre-wrap;">
        Listening for captions...
      </div>

      <div style="display:flex;margin-top:10px;gap:8px;">
        <button id="copilot-clear-btn"
          style="flex:1;background:#ff6b6b;border:none;border-radius:8px;padding:10px;color:white;font-weight:600;cursor:pointer;">
          Clear
        </button>
        <button id="copilot-generate-btn"
          style="flex:1;background:#4caf50;border:none;border-radius:8px;padding:10px;color:white;font-weight:600;cursor:pointer;">
          Generate
        </button>
      </div>

      <div id="copilot-answer"
        style="margin-top:12px;background:rgba(255,255,255,0.08);padding:10px;border-radius:8px;font-size:13px;white-space:pre-wrap;display:none;">
      </div>
    `;

    document.body.appendChild(container);

    const transcriptDiv = container.querySelector(
      "#copilot-transcript"
    ) as HTMLDivElement;
    const answerDiv = container.querySelector(
      "#copilot-answer"
    ) as HTMLDivElement;
    const clearBtn = container.querySelector(
      "#copilot-clear-btn"
    ) as HTMLButtonElement;
    const generateBtn = container.querySelector(
      "#copilot-generate-btn"
    ) as HTMLButtonElement;
    const closeBtn = container.querySelector(
      "#copilot-close-btn"
    ) as HTMLButtonElement;

    let transcriptText = "";

    function updateTranscript(text: string) {
      transcriptText = (transcriptText + " " + text).trim();
      if (!transcriptText) {
        transcriptDiv.textContent = "Listening for captions...";
      } else {
        // Keep last ~6000 chars
        if (transcriptText.length > 6000) {
          transcriptText = transcriptText.slice(transcriptText.length - 6000);
        }
        transcriptDiv.textContent = transcriptText;
      }
    }

    function showAnswer(text: string) {
      answerDiv.style.display = "block";
      answerDiv.innerText = text;
    }

    // expose helpers to outer scope
    (window as any).__copilotUpdateTranscript = updateTranscript;
    (window as any).__copilotShowAnswer = showAnswer;

    clearBtn.onclick = () => {
      transcriptText = "";
      transcriptDiv.textContent = "Listening for captions...";
      answerDiv.innerText = "";
      answerDiv.style.display = "none";
    };

    generateBtn.onclick = async () => {
      const trimmed = transcriptText.trim();
      if (!trimmed) return;
      showAnswer("⏳ Generating answer...");

      try {
        const res = await fetch("http://localhost:8000/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ transcript: trimmed }),
        });
        const data = await res.json();
        showAnswer(data.answer || "⚠️ No answer generated.");
      } catch (e) {
        console.error("[CoPilot] generate error", e);
        showAnswer("❌ Server error while generating answer.");
      }
    };

    closeBtn.onclick = () => {
      container.style.display = "none";
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createOverlay);
  } else {
    createOverlay();
  }

  // ---------- Caption capture ----------

  let lastCaption = "";
  let captionBuffer = "";
  let captionTimeout: number | undefined;

  function extractGoogleMeetCaptions(): string {
    const live = document.querySelectorAll("[data-requested-caption]");
    if (live.length > 0) {
      return Array.from(live)
        .map((el) => el.textContent?.trim() || "")
        .join(" ");
    }

    const items = document.querySelectorAll(
      "[data-speaker-id], [data-speaker-text]"
    );
    return Array.from(items)
      .map((el) => el.textContent?.trim() || "")
      .join(" ");
  }

  function extractZoomCaptions(): string {
    const items = document.querySelectorAll(
      ".transcript-view-lines__line, .transcript-view-line, .zmu-transcript-line"
    );
    return Array.from(items)
      .map((el) => el.textContent?.trim() || "")
      .filter(Boolean)
      .join(" ");
  }

  function extractTeamsCaptions(): string {
    const items = document.querySelectorAll(
      '[data-tid="closed-caption-text"], .caption-text, .ui-chat__message__content'
    );
    return Array.from(items)
      .map((el) => el.textContent?.trim() || "")
      .filter(Boolean)
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

    if (!currentCaption || currentCaption.length < 10) return;
    if (currentCaption === lastCaption) return;
    lastCaption = currentCaption;

    captionBuffer += " " + currentCaption;

    if (captionTimeout !== undefined) {
      clearTimeout(captionTimeout);
    }

    captionTimeout = window.setTimeout(() => {
      const cleaned = captionBuffer.trim();
      captionBuffer = "";
      if (!cleaned) return;

      // send to background / backend
      chrome.runtime.sendMessage({ type: "caption", text: cleaned });

      // also show in overlay transcript
      try {
        const update =
          (window as any).__copilotUpdateTranscript as
          | ((t: string) => void)
          | undefined;
        if (update) update(cleaned);
      } catch (e) {
        console.warn("[CoPilot] failed to update overlay transcript", e);
      }
    }, 1500);
  }

  // observe page changes
  const observer = new MutationObserver(() => captureCaptions());
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  // fallback polling
  setInterval(captureCaptions, 1000);

  // ---------- Receive suggestions from backend (via background) ----------

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "suggestion") {
      try {
        const show =
          (window as any).__copilotShowAnswer as
          | ((t: string) => void)
          | undefined;
        if (show) {
          // append streaming text
          const prev = (window as any).__copilot_stream_buffer || "";
          const next = prev + message.text;
          (window as any).__copilot_stream_buffer = next;
          show(next);
        }
      } catch (e) {
        console.warn("[CoPilot] failed to show suggestion", e);
      }
    }
  });
})();
