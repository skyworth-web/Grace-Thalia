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
    <div style={{ marginBottom: 8 }}>
      <label
        style={{
          display: "block",
          fontSize: "0.85rem",
          marginBottom: 4,
          fontWeight: 500,
        }}
      >
        💼 Job Description
      </label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste job description here..."
        style={{
          width: "100%",
          minHeight: "80px",
          fontSize: "0.8rem",
          padding: 6,
          border: "1px solid #ccc",
          borderRadius: 4,
          fontFamily: "inherit",
          resize: "vertical",
        }}
      />
    </div>
  );
}

