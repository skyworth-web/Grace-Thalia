import { useState, useEffect } from "react";
import ResumeUploader from "./ResumeUploader";
import JobInput from "./JobInput";
import ProfileInfo from "./ProfileInfo";

export default function Popup() {
  const [apiKey, setApiKey] = useState("");
  const [uploaded, setUploaded] = useState(false);
  const [resume, setResume] = useState("");
  const [job, setJob] = useState("");
  const [info, setInfo] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Load API key from storage on mount
  useEffect(() => {
    chrome.storage.local.get(["apiKey", "uploaded"], (result) => {
      if (result.apiKey) {
        setApiKey(result.apiKey);
      }
      if (result.uploaded) {
        setUploaded(true);
      }
    });
  }, []);

  const upload = async () => {
    if (!resume || !job) {
      setStatus("⚠️ Please upload resume and enter job description");
      return;
    }

    setIsLoading(true);
    setStatus("Uploading...");

    try {
      const response = await fetch("http://localhost:8000/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume, job, info }),
      });

      const data = await response.json();

      if (data.status === "ok") {
        setUploaded(true);
        setStatus("✅ Documents embedded successfully!");
        chrome.storage.local.set({ uploaded: true });
      } else {
        setStatus(`❌ Error: ${data.message || "Upload failed"}`);
      }
    } catch (error) {
      setStatus("❌ Failed to connect to server. Is it running on port 8000?");
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const start = () => {
    if (!apiKey) {
      setStatus("⚠️ Please enter your OpenAI API key");
      return;
    }

    // Save API key to storage
    chrome.storage.local.set({ apiKey });

    chrome.runtime.sendMessage({ action: "startSession", apiKey }, (response) => {
      if (chrome.runtime.lastError) {
        setStatus("❌ Failed to start session");
      } else {
        setStatus("✅ Co-Pilot started! Join a meeting to see suggestions.");
      }
    });
  };

  return (
    <div
      style={{
        width: 360,
        padding: 16,
        fontFamily: "system-ui, -apple-system, sans-serif",
        fontSize: "14px",
      }}
    >
      <h3 style={{ margin: "0 0 12px 0", fontSize: "18px" }}>
        🧠 Interview Co-Pilot+
      </h3>

      <div style={{ marginBottom: 12 }}>
        <label
          style={{
            display: "block",
            fontSize: "0.85rem",
            marginBottom: 4,
            fontWeight: 500,
          }}
        >
          🔑 OpenAI API Key
        </label>
        <input
          type="password"
          placeholder="sk-..."
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{
            width: "100%",
            padding: 6,
            fontSize: "0.85rem",
            border: "1px solid #ccc",
            borderRadius: 4,
            boxSizing: "border-box",
          }}
        />
      </div>

      <ProfileInfo onSave={setInfo} />
      <ResumeUploader onParsed={setResume} />
      <JobInput onChange={setJob} />

      <button
        onClick={upload}
        disabled={isLoading}
        style={{
          width: "100%",
          marginTop: 8,
          padding: 10,
          backgroundColor: "#4CAF50",
          color: "white",
          border: "none",
          borderRadius: 6,
          cursor: isLoading ? "not-allowed" : "pointer",
          fontWeight: 500,
          opacity: isLoading ? 0.6 : 1,
        }}
      >
        {isLoading ? "⏳ Processing..." : "💾 Save & Embed"}
      </button>

      {uploaded && (
        <button
          onClick={start}
          style={{
            width: "100%",
            marginTop: 8,
            padding: 10,
            backgroundColor: "#2196F3",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontWeight: 500,
          }}
        >
          ▶ Start Interview Co-Pilot
        </button>
      )}

      {status && (
        <div
          style={{
            marginTop: 12,
            padding: 8,
            fontSize: "0.8rem",
            backgroundColor: status.includes("✅")
              ? "#e8f5e9"
              : status.includes("❌")
              ? "#ffebee"
              : "#fff3e0",
            borderRadius: 4,
            color: "#333",
          }}
        >
          {status}
        </div>
      )}
    </div>
  );
}
