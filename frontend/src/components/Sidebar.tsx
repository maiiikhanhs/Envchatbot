"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import type { Conversation } from "@/types";
import styles from "./Sidebar.module.css";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  userName?: string;
  onNewChat: () => void;
  onSelect: (conv: Conversation) => void;
  onDelete: (convId: string) => void;
  onClose: () => void;
  onLogout?: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onNewChat,
  onSelect,
  onDelete,
  onClose,
}: Props) {
  const [searchTerm, setSearchTerm] = useState("");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const filteredConversations = conversations.filter((conv) =>
    conv.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const grouped = groupByDate(filteredConversations);
  const confirmConv = confirmId ? conversations.find(c => c._id === confirmId) : null;

  return (
    <div className={styles.dashboard}>
      <div className={styles.header}>
          <h2 className={styles.title}>Các cuộc trò chuyện</h2>
          <button onClick={onClose} className={styles.closeBtn} type="button">✕</button>
        </div>

        <div className={styles.statsRow}>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{conversations.length}</div>
            <div className={styles.statLabel}>Cuộc trò chuyện</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>5</div>
            <div className={styles.statLabel}>Lĩnh vực hỗ trợ</div>
          </div>
        </div>

        <div className={styles.chatHeader}>
          <h3>Lịch sử trò chuyện</h3>
          <button 
            className={styles.newChatBtn} 
            onClick={() => {
              onNewChat();
            }} 
            type="button"
          >
            + Khởi tạo mới
          </button>
        </div>

        <div className={styles.searchWrapper}>
          <div className={styles.searchContainer}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="text"
              placeholder="Tìm kiếm cuộc trò chuyện..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={styles.searchInput}
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className={styles.searchClearBtn}
                type="button"
                title="Xóa tìm kiếm"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        <div className={styles.list}>
          {grouped.map((group) => (
            <div key={group.label} className={styles.group}>
              <div className={styles.groupLabel}>{group.label}</div>
              {group.items.map((conv) => (
                <div
                  key={conv._id}
                  className={`${styles.item} ${conv._id === activeId ? styles.active : ""}`}
                  onClick={() => {
                    onSelect(conv);
                  }}
                >
                  <div className={styles.itemColorBar}></div>
                  <div className={styles.itemContent}>
                    <div className={styles.itemTitle}>{conv.title}</div>
                    <div className={styles.itemTime}>
                      {formatActualTime(conv.created_at || conv.updated_at)}
                    </div>
                  </div>
                  <button
                    className={styles.itemDelete}
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmId(conv._id);
                    }}
                    type="button"
                    title="Xóa cuộc trò chuyện"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      <line x1="10" y1="11" x2="10" y2="17" />
                      <line x1="14" y1="11" x2="14" y2="17" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          ))}

          {conversations.length === 0 && (
            <div className={styles.empty}>Chưa có cuộc trò chuyện nào</div>
          )}
        </div>

        {/* ── Confirm Delete Dialog ── */}
        {mounted && confirmId && createPortal(
          <div className={styles.confirmOverlay} onClick={() => setConfirmId(null)}>
            <div className={styles.confirmDialog} onClick={(e) => e.stopPropagation()}>
              <div className={styles.confirmIcon}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
              </div>
              <h4 className={styles.confirmTitle}>Xóa cuộc trò chuyện?</h4>
              <p className={styles.confirmText}>
                Bạn có chắc chắn muốn xóa <strong className={styles.truncateConfirmTitle}>&ldquo;{confirmConv?.title || "cuộc trò chuyện này"}&rdquo;</strong>? Hành động này không thể hoàn tác.
              </p>
              <div className={styles.confirmActions}>
                <button
                  className={styles.confirmCancel}
                  onClick={() => setConfirmId(null)}
                  type="button"
                >
                  Hủy
                </button>
                <button
                  className={styles.confirmDeleteBtn}
                  onClick={() => {
                    onDelete(confirmId);
                    setConfirmId(null);
                  }}
                  type="button"
                >
                  Xóa
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
  );
}

/* ── Helpers ──────────────────────────────────────── */

interface DateGroup {
  label: string;
  items: Conversation[];
}

function groupByDate(conversations: Conversation[]): DateGroup[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const weekAgoStart = todayStart - 7 * 86_400_000;

  const groups: Record<string, Conversation[]> = {
    "Hôm nay": [],
    "7 ngày trước": [],
    "Trước đó": [],
  };

  for (const conv of conversations) {
    const ts = new Date(conv.updated_at).getTime();
    if (Number.isNaN(ts)) {
      groups["Trước đó"].push(conv);
    } else if (ts >= todayStart) {
      groups["Hôm nay"].push(conv);
    } else if (ts >= weekAgoStart) {
      groups["7 ngày trước"].push(conv);
    } else {
      groups["Trước đó"].push(conv);
    }
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}


function formatActualTime(isoString: string): string {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";

  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();

  return `${hours}:${minutes} - ${day}/${month}/${year}`;
}
