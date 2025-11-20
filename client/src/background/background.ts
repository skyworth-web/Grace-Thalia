(function () {
  console.log("[CoPilot] background running");

  let mediaRecorder = null;
  let ws = null;

  // Listen for messages from popup or content script
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "start-audio") {
      startAudioCapture();
      sendResponse({ status: "started" });
    }
  });

  // Start capturing current tab audio
  function startAudioCapture() {
    console.log("[CoPilot] Starting tab audio capture...");

    chrome.tabCapture.capture(
      { audio: true, video: false },
      (stream) => {
        if (!stream) {
          console.error("[CoPilot] tabCapture failed");
          return;
        }

        console.log("[CoPilot] Tab audio stream acquired");

        startRecording(stream);
      }
    );
  }

  function startRecording(stream) {
    try {
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm; codecs=opus",
        audioBitsPerSecond: 32000
      });

      mediaRecorder.ondataavailable = async (event) => {
        if (!event.data.size) return;

        // Send chunk to backend
        await sendAudioToServer(event.data);
      };

      // Record small chunks
      mediaRecorder.start(1000); // 1-second chunks

      console.log("[CoPilot] MediaRecorder started");
    } catch (err) {
      console.error("[CoPilot] Failed to start MediaRecorder", err);
    }
  }

  async function sendAudioToServer(blob) {
    try {
      const formData = new FormData();
      formData.append("file", blob, "chunk.webm");

      const res = await fetch("http://localhost:8000/stt", {
        method: "POST",
        body: formData
      });

      const data = await res.json();

      if (data.transcript && data.transcript.trim() !== "") {
        console.log("[CoPilot STT] →", data.transcript);

        // Forward transcript to all tabs
        chrome.tabs.query({}, (tabs) => {
          for (const tab of tabs) {
            chrome.tabs.sendMessage(tab.id, {
              type: "transcript",
              text: data.transcript
            });
          }
        });
      }
    } catch (err) {
      console.error("[CoPilot] STT upload error", err);
    }
  }

})();
