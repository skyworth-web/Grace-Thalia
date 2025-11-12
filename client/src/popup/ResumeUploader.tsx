import { useState, useRef } from "react";
import * as pdfjsLib from "pdfjs-dist";
import mammoth from "mammoth";

// Configure PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

interface ResumeUploaderProps {
  onParsed: (text: string) => void;
}

export default function ResumeUploader({ onParsed }: ResumeUploaderProps) {
  const [status, setStatus] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parsePDF = async (file: File): Promise<string> => {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let text = "";

    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();
      text += textContent.items.map((item: any) => item.str).join(" ") + "\n";
    }
    return text;
  };

  const parseDOCX = async (file: File): Promise<string> => {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value;
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("Parsing...");
    try {
      let text = "";
      if (file.type === "application/pdf") {
        text = await parsePDF(file);
      } else if (
        file.type ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      ) {
        text = await parseDOCX(file);
      } else if (file.type === "text/plain") {
        text = await file.text();
      } else {
        setStatus("Unsupported file type");
        return;
      }

      onParsed(text);
      setStatus(`✓ Parsed ${file.name}`);
    } catch (err) {
      setStatus("Error parsing file");
      console.error(err);
    }
  };

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
        📄 Resume (PDF/DOCX/TXT)
      </label>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={handleFile}
        style={{ width: "100%", fontSize: "0.8rem" }}
      />
      {status && (
        <div style={{ fontSize: "0.75rem", color: "#666", marginTop: 4 }}>
          {status}
        </div>
      )}
    </div>
  );
}

