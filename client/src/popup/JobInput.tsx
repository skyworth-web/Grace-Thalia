// JobInput.tsx
import { useState, useEffect } from "react";

interface JobInputProps {
  onChange: (text: string) => void;
}

export default function JobInput({ onChange }: JobInputProps) {
  const [text, setText] = useState("");

  useEffect(() => {
    onChange(text);
  }, [text, onChange]);

  return (
    <div style={{ marginBottom: "16px" }}>
      <label
        style={{
          display: "block",
          fontSize: "14px",
          marginBottom: "8px",
          fontWeight: 600,
          color: "#2d3748",
        }}
      >
        <span style={{ 
          marginRight: "8px",
          fontSize: "16px"
        }}>💼</span>
        Job Description <span style={{ color: "#718096", fontWeight: 500 }}>(Optional)</span>
      </label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste the job description here to get tailored interview suggestions..."
        style={{
          width: "100%",
          minHeight: "100px",
          fontSize: "14px",
          padding: "12px",
          border: "1px solid #e2e8f0",
          borderRadius: "12px",
          fontFamily: "inherit",
          resize: "vertical",
          background: "#f7fafc",
          transition: "all 0.2s ease",
          outline: "none",
          boxSizing: "border-box"
        }}
        onFocus={(e) => {
          e.target.style.background = "white";
          e.target.style.borderColor = "#4299e1";
          e.target.style.boxShadow = "0 0 0 3px rgba(66, 153, 225, 0.1)";
        }}
        onBlur={(e) => {
          e.target.style.background = "#f7fafc";
          e.target.style.borderColor = "#e2e8f0";
          e.target.style.boxShadow = "none";
        }}
      />
      <div style={{
        fontSize: "12px",
        color: "#718096",
        marginTop: "4px",
        textAlign: "right"
      }}>
        {text.length} characters
      </div>
    </div>
  );
}