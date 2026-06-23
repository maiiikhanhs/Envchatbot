"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import type { ChatMessage, Conversation } from "@/types";
import { useAuth } from "@/components/AuthProvider";
import {
  deleteConversation,
  fetchConversations,
  fetchMessages,
  sendChat,
} from "@/services/api";
import Sidebar from "@/components/Sidebar";
import ChatArea from "@/components/ChatArea";
import ChatInput from "@/components/ChatInput";
import ReportModal from "@/components/ReportModal";

export default function HomePage() {
  const { user, isLoading: authLoading, logout } = useAuth();
  const router = useRouter();

  /* ── State ───────────────────────────────────────── */
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(generateId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [mounted, setMounted] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  /* ── Mount detection ─────────────────────────────── */
  useEffect(() => {
    setMounted(true);
  }, []);

  /* ── Close dropdown when clicking outside ────────── */
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /* ── Auth guard ──────────────────────────────────── */
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  /* ── Load conversations on mount ─────────────────── */
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const data = await fetchConversations();
      setConversations(data);
    } catch {
      // API not available yet — that's okay for now
    }
  };

  /* ── Handlers ────────────────────────────────────── */

  const handleNewChat = useCallback(() => {
    setActiveConvId(null);
    setSessionId(generateId());
    setMessages([]);
  }, []);

  const handleSelectConversation = useCallback(async (conv: Conversation) => {
    setActiveConvId(conv._id);
    setSessionId(conv.session_id);

    try {
      console.log("Selected conversation:", conv);
      console.log("Fetching messages for ID:", conv._id);
      const data = await fetchMessages(conv._id);
      console.log("Fetched messages data:", data);

      const mapped: ChatMessage[] = data.map((msg) => ({
        id: msg._id,
        role: msg.role,
        content: msg.role === "user" ? msg.question : msg.answer,
        routerLabel: msg.router_label || undefined,
        fileName: undefined,
        timestamp: msg.created_at,
        sources: (msg as any).retrieved_chunks || undefined,
      }));
      setMessages(mapped);
    } catch (err) {
      console.error("Error fetching messages:", err);
      setMessages([]);
    }
  }, []);

  const handleDeleteConversation = useCallback(
    async (convId: string) => {
      try {
        await deleteConversation(convId);
        setConversations((prev) => prev.filter((c) => c._id !== convId));
        if (activeConvId === convId) {
          handleNewChat();
        }
      } catch {
        // silently fail
      }
    },
    [activeConvId, handleNewChat],
  );

  const handleSend = useCallback(
    async (question: string, file: File | null) => {
      // Add user message to UI immediately
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: question,
        fileName: file?.name,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const response = await sendChat(question, sessionId, file);

        // Update conversation ID if new
        if (response.conversation_id) {
          setActiveConvId(response.conversation_id);
          setSessionId(response.session_id);
        }

        // Add assistant message with simulated typing
        const assistantMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: response.answer || "Không nhận được phản hồi từ hệ thống.",
          routerLabel: response.router_label || undefined,
          timestamp: new Date().toISOString(),
          sources: response.retrieved_chunks || undefined,
        };

        setIsLoading(false);
        // Refresh conversation list immediately
        loadConversations();

        await simulateTyping(assistantMsg, setMessages);
      } catch (error) {
        setIsLoading(false);
        const errorMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "Có lỗi khi kết nối đến hệ thống. Vui lòng kiểm tra backend API đã chạy chưa.",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    },
    [sessionId],
  );

  const handleSuggestionClick = useCallback(
    (text: string) => {
      handleSend(text, null);
    },
    [handleSend],
  );

  const handleLogout = useCallback(() => {
    logout();
    router.push("/login");
  }, [logout, router]);

  /* ── Render ──────────────────────────────────────── */

  if (authLoading || !user) {
    return null; // Wait for auth check
  }

  return (
    <div className="appContainer">
      {/* Top bar */}
      <header className="topbar">
        <div className="topbarLeft">
          🌿 EnvChat
        </div>
        <div className="topbarCenter">
          <button
            className={`topTab ${!sidebarOpen ? 'active' : ''}`}
            onClick={() => setSidebarOpen(false)}
            type="button"
          >
            Trò chuyện
          </button>
          <button
            className={`topTab ${sidebarOpen ? 'active' : ''}`}
            onClick={() => setSidebarOpen(true)}
            type="button"
          >
            Lịch sử
          </button>
        </div>
        <div className="topbarRight">
          <div className="userMenuContainer" ref={userMenuRef}>
            <button
              className="topbarAvatar"
              onClick={() => setShowUserMenu(!showUserMenu)}
              type="button"
              title="Tài khoản"
            >
              {user.displayName.charAt(0).toUpperCase()}
            </button>

            {showUserMenu && (
              <div className="userDropdown">
                <div className="userInfo">
                  <div className="userName">{user.displayName}</div>
                </div>
                <button
                  className="dropdownReportBtn"
                  onClick={() => {
                    setShowUserMenu(false);
                    setShowReportModal(true);
                  }}
                  type="button"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect width="18" height="18" x="3" y="3" rx="2" />
                    <path d="M12 8v4" />
                    <path d="M12 16h.01" />
                  </svg>
                  Báo lỗi & góp ý
                </button>
                <button
                  className="dropdownLogoutBtn"
                  onClick={() => {
                    setShowUserMenu(false);
                    setShowLogoutConfirm(true);
                  }}
                  type="button"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                  Đăng xuất
                </button>
              </div>
            )}
          </div>
          <button
            className="topbarHamburger"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            type="button"
          >
            ☰
          </button>
        </div>
      </header>

      <div className="mainSplit">
        {/* Left: Chat Section */}
        <main className="chatSection">
          <ChatArea
            messages={messages}
            isLoading={isLoading}
            onSuggestionClick={handleSuggestionClick}
            userName={user.displayName}
          />
          <ChatInput onSend={handleSend} disabled={isLoading} />
        </main>

        {/* External Overlay for Sidebar */}
        {sidebarOpen && (
          <div className="sidebarOverlay" onClick={() => setSidebarOpen(false)} />
        )}

        {/* Right: Dashboard Section (formerly Sidebar) */}
        <aside className={`dashboardSection ${sidebarOpen ? 'open' : ''}`}>
          <Sidebar
            conversations={conversations}
            activeId={activeConvId}
            userName={user.displayName}
            onNewChat={handleNewChat}
            onSelect={handleSelectConversation}
            onDelete={handleDeleteConversation}
            onClose={() => setSidebarOpen(false)}
            onLogout={() => setShowLogoutConfirm(true)}
          />
        </aside>

        {/* ── Global Logout Confirm Dialog ── */}
        {mounted && showLogoutConfirm && createPortal(
          <div className="globalConfirmOverlay" onClick={() => setShowLogoutConfirm(false)}>
            <div className="globalConfirmDialog" onClick={(e) => e.stopPropagation()}>
              <div className="globalConfirmIcon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </div>
              <h4 className="globalConfirmTitle">Đăng xuất tài khoản?</h4>
              <p className="globalConfirmText">
                Bạn có chắc chắn muốn đăng xuất khỏi hệ thống?
              </p>
              <div className="globalConfirmActions">
                <button
                  className="globalConfirmCancel"
                  onClick={() => setShowLogoutConfirm(false)}
                  type="button"
                >
                  Hủy
                </button>
                <button
                  className="globalConfirmActionBtn"
                  onClick={() => {
                    setShowLogoutConfirm(false);
                    handleLogout();
                  }}
                  type="button"
                >
                  Đăng xuất
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

        {/* ── Report & Feedback Modal ── */}
        <ReportModal
          isOpen={showReportModal}
          onClose={() => setShowReportModal(false)}
        />
      </div>
    </div>
  );
}

/* ── Utilities ───────────────────────────────────── */

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
}

async function simulateTyping(
  msg: ChatMessage,
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
): Promise<void> {
  const words = msg.content.split(" ");
  let displayed = "";

  for (let i = 0; i < words.length; i++) {
    displayed += (i > 0 ? " " : "") + words[i];
    const partial: ChatMessage = { ...msg, content: displayed };

    setMessages((prev) => {
      const existing = prev.findIndex((m) => m.id === msg.id);
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = partial;
        return updated;
      }
      return [...prev, partial];
    });

    const delay = words.length > 100 ? 10 : 30;
    await new Promise((r) => setTimeout(r, delay));
  }
}
