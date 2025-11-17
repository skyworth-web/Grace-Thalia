import { useState, useRef } from "react";
import * as pdfjsLib from "pdfjs-dist";
import mammoth from "mammoth";

// Configure PDF.js worker for Chrome extension
// Try to use the worker from the extension's dist folder
// Fallback to CDN if local worker not available
try {
  // In Chrome extension, use chrome.runtime.getURL to get the worker path
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('pdf.worker.min.js');
  } else {
    // Fallback for development or if chrome API not available
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;
  }
} catch (e) {
  // Final fallback to CDN
  pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;
}

interface ResumeUploaderProps {
  onParsed: (text: string) => void;
}

export default function ResumeUploader({ onParsed }: ResumeUploaderProps) {
  const [status, setStatus] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parsePDF = async (file: File): Promise<string> => {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const loadingTask = pdfjsLib.getDocument({ 
        data: arrayBuffer,
        verbosity: 0 // Suppress console warnings
      });
      const pdf = await loadingTask.promise;
      let text = "";

      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();
        const pageText = textContent.items
          .map((item: any) => item.str || "")
          .filter((str: string) => str.trim().length > 0)
          .join(" ");
        if (pageText.trim()) {
          text += pageText + "\n\n";
        }
      }
      return text.trim();
    } catch (error: any) {
      console.error("PDF parsing error:", error);
      throw new Error(`Failed to parse PDF: ${error.message || "Unknown error"}`);
    }
  };

  const parseDOCX = async (file: File): Promise<string> => {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const result = await mammoth.extractRawText({ arrayBuffer });
      
      if (result.messages && result.messages.length > 0) {
        console.warn("DOCX parsing warnings:", result.messages);
      }
      
      if (!result.value || result.value.trim().length === 0) {
        throw new Error("No text could be extracted from the document");
      }
      
      return result.value.trim();
    } catch (error: any) {
      console.error("DOCX parsing error:", error);
      throw new Error(`Failed to parse DOCX: ${error.message || "Unknown error"}`);
    }
  };

  const handleFile = async (file: File) => {
    if (!file) return;

    setFileName(file.name);
    setStatus("Parsing document...");
    
    try {
      let text = "";
      const fileName = file.name.toLowerCase();
      const fileType = file.type.toLowerCase();

      // Determine file type by extension if MIME type is not available
      if (fileType === "application/pdf" || fileName.endsWith(".pdf")) {
        text = await parsePDF(file);
      } else if (
        fileType === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
        fileType === "application/msword" ||
        fileName.endsWith(".docx") ||
        fileName.endsWith(".doc")
      ) {
        text = await parseDOCX(file);
      } else if (fileType === "text/plain" || fileName.endsWith(".txt")) {
        text = await file.text();
      } else {
        setStatus(`❌ Unsupported file type. Please use PDF, DOCX, or TXT.`);
        setFileName("");
        return;
      }

      if (!text || text.trim().length === 0) {
        setStatus("⚠️ File appears to be empty or could not extract text");
        setFileName("");
        return;
      }

      onParsed(text);
      setStatus(`✅ Successfully parsed resume (${text.length.toLocaleString()} characters)`);
    } catch (err: any) {
      const errorMsg = err?.message || "Unknown error";
      setStatus(`❌ Error parsing file: ${errorMsg}`);
      setFileName("");
      console.error("Resume parsing error:", err);
      
      // Provide more helpful error messages
      if (errorMsg.includes("worker") || errorMsg.includes("pdf.worker")) {
        setStatus("❌ PDF parser error. Please try a different file format.");
      } else if (errorMsg.includes("mammoth")) {
        setStatus("❌ DOCX parser error. Please try saving as PDF or TXT.");
      }
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await handleFile(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      await handleFile(files[0]);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const getFileIcon = () => {
    if (!fileName) return "📄";
    const ext = fileName.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return "📕";
    if (ext === 'docx' || ext === 'doc') return "📘";
    if (ext === 'txt') return "📃";
    return "📄";
  };

  return (
    <div style={{ marginBottom: "20px" }}>
      <label
        style={{
          display: "block",
          fontSize: "14px",
          marginBottom: "8px",
          fontWeight: 600,
          color: "#2d3748",
        }}
      >
        <span style={{ marginRight: "8px", fontSize: "16px" }}>📄</span>
        Upload Resume
        <span style={{ color: "#718096", fontWeight: 500, marginLeft: "4px" }}>
          (PDF/DOCX/TXT)
        </span>
      </label>

      {/* File Upload Area */}
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          width: "70vw",
          minHeight: "120px",
          border: isDragging ? "2px dashed #4299e1" : "2px dashed #cbd5e0",
          borderRadius: "12px",
          background: isDragging 
            ? "linear-gradient(135deg, #ebf8ff 0%, #bee3f8 100%)"
            : fileName 
            ? "linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%)"
            : "linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transition: "all 0.3s ease",
          padding: "20px",
          textAlign: "center",
          position: "relative",
          overflow: "hidden"
        }}
        onMouseEnter={(e) => {
          if (!fileName) {
            e.currentTarget.style.background = "linear-gradient(135deg, #ebf8ff 0%, #bee3f8 100%)";
            e.currentTarget.style.borderColor = "#4299e1";
          }
        }}
        onMouseLeave={(e) => {
          if (!fileName) {
            e.currentTarget.style.background = "linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)";
            e.currentTarget.style.borderColor = "#cbd5e0";
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          onChange={handleFileInput}
          style={{ display: "none" }}
        />

        {fileName ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "32px", marginBottom: "8px" }}>
              {getFileIcon()}
            </div>
            <div style={{ 
              fontSize: "14px", 
              fontWeight: 600, 
              color: "#22543d",
              marginBottom: "4px",
              wordBreak: "break-word"
            }}>
              {fileName}
            </div>
            <div style={{ 
              fontSize: "12px", 
              color: "#38a169",
              fontWeight: 500
            }}>
              ✓ Ready for processing
            </div>
          </div>
        ) : (
          <>
            <div style={{ fontSize: "32px", marginBottom: "12px" }}>
              📄
            </div>
            <div style={{ 
              fontSize: "14px", 
              fontWeight: 600, 
              color: "#4a5568",
              marginBottom: "4px"
            }}>
              Click to upload or drag and drop
            </div>
            <div style={{ 
              fontSize: "12px", 
              color: "#718096",
              lineHeight: "1.4"
            }}>
              Supports PDF, DOCX, and TXT files
            </div>
          </>
        )}
      </div>

      {/* Status Message */}
      {status && (
        <div
          style={{
            marginTop: "12px",
            padding: "10px 12px",
            fontSize: "13px",
            background: status.includes("✅")
              ? "linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%)"
              : status.includes("❌")
              ? "linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%)"
              : status.includes("⚠️")
              ? "linear-gradient(135deg, #feebc8 0%, #fbd38d 100%)"
              : "linear-gradient(135deg, #e9d8fd 0%, #d6bcfa 100%)",
            borderRadius: "8px",
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
            textAlign: "center"
          }}
        >
          {status}
        </div>
      )}

      {/* File Requirements */}
      <div style={{
        marginTop: "8px",
        fontSize: "11px",
        color: "#718096",
        textAlign: "center",
        lineHeight: "1.4"
      }}>
        Maximum file size: 10MB • Supported: PDF, DOCX, DOC, TXT
      </div>
    </div>
  );
}