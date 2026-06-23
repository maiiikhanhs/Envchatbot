"use client";

import { useRef, useState } from "react";
import styles from "./ChatInput.module.css";

interface Props {
  onSend: (question: string, file: File | null) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSend = text.trim().length > 0 && !disabled;

  const handleSend = () => {
    if (!canSend) return;
    onSend(text.trim(), file);
    setText("");
    setFile(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 150)}px`;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
  };

  const removeFile = () => {
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.inner}>
        {/* File preview */}
        {file && (
          <div className={styles.filePreview}>
            <span>📎</span>
            <span className={styles.fileName}>{file.name}</span>
            <button
              className={styles.removeFile}
              onClick={removeFile}
              type="button"
            >
              ✕
            </button>
          </div>
        )}

        {/* Input container */}
        <div className={styles.inputContainer}>
          <button
            className={styles.attachBtn}
            onClick={() => fileInputRef.current?.click()}
            title="Đính kèm file (.pdf, .docx)"
            type="button"
          >
            📎
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            className={styles.fileInput}
            onChange={handleFileChange}
          />
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            placeholder="Hỏi về quan trắc môi trường..."
            rows={1}
            value={text}
            onChange={handleTextareaInput}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={!canSend}
            title="Gửi"
            type="button"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}
