// Popup.tsx
import { useState, useEffect } from "react";
import ResumeUploader from "./ResumeUploader";
import JobInput from "./JobInput";

export default function Popup() {
  const [uploaded, setUploaded] = useState(false);
  const [resume, setResume] = useState("");
  const [job, setJob] = useState("");
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Load uploaded state on mount
  useEffect(() => {
    chrome.storage.local.get(["uploaded"], (result) => {
      if (result.uploaded) {
        setUploaded(true);
      }
    });
  }, []);

  const upload = async () => {
    if (!resume) {
      setStatus("⚠️ Please upload your resume");
      return;
    }

    setIsLoading(true);
    setStatus("Uploading...");

    try {
      const response = await fetch("http://localhost:8000/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume, job: job || "" }),
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
    setStatus("🔄 Connecting to backend...");
    
    chrome.runtime.sendMessage({ action: "startSession" }, (response) => {
      if (chrome.runtime.lastError) {
        setStatus(`❌ Failed to start session: ${chrome.runtime.lastError.message}`);
        console.error("Background script error:", chrome.runtime.lastError);
      } else if (response) {
        if (response.success) {
          setStatus("✅ Co-Pilot started! Join a meeting to see suggestions.");
        } else {
          setStatus(`❌ ${response.message || "Failed to start session"}`);
        }
      } else {
        // No response received (might be async)
        setStatus("🔄 Starting session...");
        // Check connection status after a delay
        setTimeout(() => {
          setStatus("✅ Co-Pilot started! Join a meeting to see suggestions.");
        }, 1000);
      }
    });
  };

  return (
    <div
      style={{
        width: "100%",
        minHeight: "400px",
        padding: "20px",
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        fontSize: "14px",
        background: "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
        boxSizing: "border-box",
      }}
    >
      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        marginBottom: "20px",
        paddingBottom: "16px",
        borderBottom: "1px solid rgba(255, 255, 255, 0.3)"
      }}>
        <div style={{
          width: "44px",
          height: "44px",
          borderRadius: "12px",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginRight: "14px",
          fontSize: "22px",
          boxShadow: "0 4px 12px rgba(102, 126, 234, 0.3)"
        }}>
          🧠
        </div>
        <div>
          <h3 style={{ 
            margin: 0, 
            fontSize: "18px", 
            fontWeight: 700,
            color: "#2d3748",
            letterSpacing: "-0.02em"
          }}>
            Interview Co-Pilot+
          </h3>
          <p style={{ 
            margin: 0, 
            fontSize: "12px", 
            color: "#718096",
            opacity: 0.9,
            fontWeight: 500
          }}>
            AI-powered interview assistant
          </p>
        </div>
      </div>

      {/* Content Area */}
      <div style={{
        background: "white",
        borderRadius: "16px",
        padding: "20px",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.1)",
        marginBottom: "16px",
        border: "1px solid rgba(255, 255, 255, 0.2)"
      }}>
        <ResumeUploader onParsed={setResume} />
        <JobInput onChange={setJob} />

        {/* Upload Button */}
        <button
          onClick={upload}
          disabled={isLoading}
          style={{
            width: "100%",
            marginTop: "16px",
            padding: "14px 20px",
            background: isLoading 
              ? "linear-gradient(135deg, #a0aec0 0%, #718096 100%)"
              : "linear-gradient(135deg, #48bb78 0%, #38a169 100%)",
            color: "white",
            border: "none",
            borderRadius: "12px",
            cursor: isLoading ? "not-allowed" : "pointer",
            fontWeight: 600,
            fontSize: "14px",
            opacity: isLoading ? 0.7 : 1,
            transition: "all 0.3s ease",
            boxShadow: isLoading 
              ? "0 2px 8px rgba(160, 174, 192, 0.3)"
              : "0 4px 14px rgba(72, 187, 120, 0.4)",
            position: "relative",
            overflow: "hidden"
          }}
          onMouseEnter={(e) => {
            if (!isLoading) {
              e.target.style.transform = "translateY(-2px)";
              e.target.style.boxShadow = "0 6px 20px rgba(72, 187, 120, 0.5)";
            }
          }}
          onMouseLeave={(e) => {
            if (!isLoading) {
              e.target.style.transform = "translateY(0)";
              e.target.style.boxShadow = "0 4px 14px rgba(72, 187, 120, 0.4)";
            }
          }}
        >
          {isLoading ? (
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ 
                width: "18px", 
                height: "18px", 
                border: "2px solid transparent",
                borderTop: "2px solid white",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
                marginRight: "10px"
              }}></span>
              Processing Documents...
            </span>
          ) : (
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ marginRight: "10px", fontSize: "16px" }}>💾</span>
              Save & Embed Documents
            </span>
          )}
        </button>

        {/* Start Button */}
        {uploaded && (
          <button
            onClick={start}
            style={{
              width: "100%",
              marginTop: "12px",
              padding: "14px 20px",
              background: "linear-gradient(135deg, #4299e1 0%, #3182ce 100%)",
              color: "white",
              border: "none",
              borderRadius: "12px",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "14px",
              transition: "all 0.3s ease",
              boxShadow: "0 4px 14px rgba(66, 153, 225, 0.4)"
            }}
            onMouseEnter={(e) => {
              e.target.style.transform = "translateY(-2px)";
              e.target.style.boxShadow = "0 6px 20px rgba(66, 153, 225, 0.5)";
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = "translateY(0)";
              e.target.style.boxShadow = "0 4px 14px rgba(66, 153, 225, 0.4)";
            }}
          >
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ marginRight: "10px", fontSize: "16px" }}>🚀</span>
              Start Interview Co-Pilot
            </span>
          </button>
        )}
      </div>

      {/* Status Message */}
      {status && (
        <div
          style={{
            marginTop: "16px",
            padding: "14px 16px",
            fontSize: "13px",
            background: status.includes("✅")
              ? "linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%)"
              : status.includes("❌")
              ? "linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%)"
              : status.includes("⚠️")
              ? "linear-gradient(135deg, #feebc8 0%, #fbd38d 100%)"
              : "linear-gradient(135deg, #e9d8fd 0%, #d6bcfa 100%)",
            borderRadius: "12px",
            color: status.includes("✅")
              ? "#22543d"
              : status.includes("❌")
              ? "#742a2a"
              : status.includes("⚠️")
              ? "#744210"
              : "#44337a",
            border: status.includes("✅")
              ? "1px solid #9ae6b4"
              : status.includes("❌")
              ? "1px solid #feb2b2"
              : status.includes("⚠️")
              ? "1px solid #fbd38d"
              : "1px solid #d6bcfa",
            fontWeight: 500,
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}
        >
          {status}
        </div>
      )}

      {/* CSS for spinner animation */}
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  );
}