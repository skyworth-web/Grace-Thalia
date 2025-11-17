import { useEffect, useState } from "react";

export default function Overlay() {
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState("");
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const listener = (e: any) => {
      setText((prev) =>
        (prev + "\n" + e.detail).slice(-6000)
      );
    };

    window.addEventListener("copilot-suggestion", listener);
    return () => window.removeEventListener("copilot-suggestion", listener);
  }, []);

  const clearText = () => {
    setText("");
    setAnswer("");
  };

  const generate = async () => {
    if (!text.trim()) return;

    setAnswer("⏳ Generating answer...");

    try {
      const res = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: text })
      });

      const data = await res.json();
      setAnswer(data.answer || "⚠️ No answer produced.");
    } catch {
      setAnswer("❌ Server error.");
    }
  };

  if (!visible) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "20px",
        right: "20px",
        width: "380px",
        height: "420px",
        background: "rgba(20, 20, 20, 0.75)",
        backdropFilter: "blur(12px)",
        color: "white",
        zIndex: 999999999,
        borderRadius: "14px",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, sans-serif",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)"
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong style={{ fontSize: "14px", opacity: 0.9 }}>
          🧠 Interview Co-Pilot
        </strong>

        <button
          onClick={() => setVisible(false)}
          style={{
            background: "transparent",
            border: "none",
            fontSize: "20px",
            cursor: "pointer",
            color: "white",
            opacity: 0.6
          }}
        >
          ×
        </button>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          marginTop: "10px",
          whiteSpace: "pre-wrap",
          fontSize: "13px",
        }}
      >
        {text || "Listening for captions..."}
      </div>

      <div style={{ display: "flex", marginTop: "10px", gap: "8px" }}>
        <button
          onClick={clearText}
          style={{
            flex: 1,
            padding: "10px",
            borderRadius: "8px",
            border: "none",
            background: "#ff5252",
            color: "white",
            cursor: "pointer",
            fontWeight: 600
          }}
        >
          Clear
        </button>

        <button
          onClick={generate}
          style={{
            flex: 1,
            padding: "10px",
            borderRadius: "8px",
            border: "none",
            background: "#4CAF50",
            color: "white",
            cursor: "pointer",
            fontWeight: 600
          }}
        >
          Generate
        </button>
      </div>

      {answer && (
        <div
          style={{
            marginTop: "12px",
            background: "rgba(255,255,255,0.1)",
            padding: "10px",
            borderRadius: "8px",
            fontSize: "13px",
            whiteSpace: "pre-wrap"
          }}
        >
          <strong>AI Answer:</strong>
          <br />
          {answer}
        </div>
      )}
    </div>
  );
}
