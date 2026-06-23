"use client";

import React, { useState } from "react";
import styles from "./ReportModal.module.css";
import { submitReport } from "@/services/api";

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type CategoryType = "bug" | "suggestion" | "feature";

export default function ReportModal({ isOpen, onClose }: ReportModalProps) {
  const [activeTab, setActiveTab] = useState<CategoryType>("bug");
  const [description, setDescription] = useState("");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  if (!isOpen) return null;

  const handleClose = () => {
    setActiveTab("bug");
    setDescription("");
    setAttachedFile(null);
    setFileError(null);
    setSubmitError(null);
    setIsSubmitting(false);
    setIsSuccess(false);
    onClose();
  };

  const getPlaceholder = () => {
    if (activeTab === "bug") return "Nhập mô tả lỗi bạn gặp phải tại đây... (tối thiểu 20 ký tự)";
    if (activeTab === "suggestion") return "Nhập góp ý, ý kiến của bạn để cải thiện sản phẩm... (tối thiểu 20 ký tự)";
    return "Mô tả tính năng bạn muốn có trong sản phẩm... (tối thiểu 20 ký tự)";
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate size (5MB limit)
    if (file.size > 5 * 1024 * 1024) {
      setFileError("Kích thước tệp vượt quá 5MB.");
      return;
    }

    // Validate format
    const allowedTypes = ["image/png", "image/jpeg", "image/jpg"];
    if (!allowedTypes.includes(file.type)) {
      setFileError("Chỉ hỗ trợ tệp ảnh PNG, JPG.");
      return;
    }

    setAttachedFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (description.length < 20 || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await submitReport({
        reportType: activeTab,
        content: description,
        attachment: attachedFile,
        clientContext: typeof window !== "undefined" ? { page_url: window.location.href } : {},
      });
      setIsSuccess(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Không gửi được báo cáo");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={handleClose}>
      <div className={styles.modalContainer} onClick={(e) => e.stopPropagation()}>
        {isSuccess ? (
          /* ── SUCCESS VIEW ── */
          <div className={styles.successContainer}>
            <div className={styles.successIconCircle}>
              <span style={{ fontSize: "28px" }}>✓</span>
            </div>
            <h3 className={styles.successTitle}>Gửi báo cáo thành công!</h3>
            <p className={styles.successMessage}>
              Cảm ơn bạn đã đóng góp ý kiến để hoàn thiện sản phẩm.
            </p>
            <button className={styles.successCloseButton} onClick={handleClose} type="button">
              Đóng
            </button>
          </div>
        ) : (
          /* ── FORM VIEW ── */
          <form onSubmit={handleSubmit}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Báo lỗi & Góp ý</h3>
              <button className={styles.closeButton} onClick={handleClose} type="button" aria-label="Close">
                ✕
              </button>
            </div>
            <p className={styles.modalSubtitle}>
              Chúng tôi luôn lắng nghe ý kiến của bạn để cải thiện sản phẩm.
            </p>

            {/* Category selection tabs */}
            <div className={styles.tabsContainer}>
              <button
                type="button"
                className={`${styles.tabButton} ${activeTab === "bug" ? styles.tabButtonActive : ""}`}
                onClick={() => setActiveTab("bug")}
              >
                🪲 Báo lỗi
              </button>
              <button
                type="button"
                className={`${styles.tabButton} ${activeTab === "suggestion" ? styles.tabButtonActive : ""}`}
                onClick={() => setActiveTab("suggestion")}
              >
                💬 Góp ý
              </button>
              <button
                type="button"
                className={`${styles.tabButton} ${activeTab === "feature" ? styles.tabButtonActive : ""}`}
                onClick={() => setActiveTab("feature")}
              >
                👍 Tính năng
              </button>
            </div>

            {/* Description area */}
            <div className={styles.formGroup}>
              <label className={styles.inputLabel} htmlFor="report-description">
                Mô tả chi tiết <span className={styles.requiredStar}>*</span>
              </label>
              <textarea
                id="report-description"
                className={styles.textarea}
                placeholder={getPlaceholder()}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={1000}
                required
              />
              <div className={`${styles.charCount} ${description.length > 0 && description.length < 20 ? styles.charCountError : ""}`}>
                {description.length}/1000 ký tự (tối thiểu 20 ký tự)
              </div>
            </div>

            {/* Simplified Upload File Box */}
            <div className={styles.uploadDropzone} onClick={() => document.getElementById("file-upload")?.click()}>
              <input
                id="file-upload"
                type="file"
                onChange={handleFileChange}
                accept=".png,.jpg,.jpeg"
                style={{ display: "none" }}
              />
              {attachedFile ? (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", justifyContent: "center" }}>
                  <span>📁 {attachedFile.name} ({(attachedFile.size / 1024 / 1024).toFixed(1)} MB)</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setAttachedFile(null);
                    }}
                    style={{ background: "none", border: "none", cursor: "pointer", fontSize: "14px" }}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <>
                  <span style={{ fontSize: "20px" }}>📤</span>
                  <p className={styles.uploadTitle}>Nhấn để tải lên tệp hoặc Ảnh chụp màn hình</p>
                  <p className={styles.uploadSubtitle}>Hỗ trợ định dạng: PNG, JPG (tối đa 5MB)</p>
                </>
              )}
              {fileError && <p className={styles.charCountError} style={{ fontSize: "11px", marginTop: "4px" }}>{fileError}</p>}
            </div>
            {submitError && <p className={styles.charCountError} style={{ marginTop: "-12px", marginBottom: "12px" }}>{submitError}</p>}

            {/* Action Buttons */}
            <div className={styles.actions}>
              <button className={styles.cancelButton} onClick={handleClose} type="button">
                Hủy
              </button>
              <button
                className={styles.submitButton}
                type="submit"
                disabled={description.length < 20 || isSubmitting}
              >
                {isSubmitting ? "Đang gửi..." : "Gửi báo cáo →"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
