import type { ChatResponse, Conversation, Message } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const stored = localStorage.getItem("envchat_user");
    if (stored) {
      const user = JSON.parse(stored);
      if (user && user.username) {
        return { "X-User-Id": user.username };
      }
    }
  } catch {
    // ignore
  }
  return {};
}

/* ── Auth ─────────────────────────────────────────── */

export interface AuthResponse {
  status: string;
  message: string;
  user?: {
    id: string;
    username: string;
    display_name: string;
  };
}

export async function loginApi(
  username: string,
  password: string,
): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return res.json();
}

export async function registerApi(
  username: string,
  password: string,
): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/api/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return res.json();
}

/* ── Chat ────────────────────────────────────────── */

export async function sendChat(
  question: string,
  sessionId: string,
  file?: File | null,
): Promise<ChatResponse> {
  const formData = new FormData();
  formData.append("question", question);
  formData.append("session_id", sessionId);
  if (file) {
    formData.append("file", file);
  }

  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { ...getAuthHeaders() },
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  const data: ChatResponse = await res.json();

  if (data.status !== "success") {
    throw new Error(data.message || "Chat request failed");
  }

  return data;
}

/* ── Reports ────────────────────────────────────── */

export interface ReportRequest {
  reportType: "bug" | "suggestion" | "feature";
  content: string;
  conversationId?: string;
  messageId?: string;
  clientContext?: Record<string, unknown>;
  attachment?: File | null;
}

export async function submitReport(payload: ReportRequest): Promise<{ status: string; report_id: string; message: string }> {
  const formData = new FormData();
  formData.append("report_type", payload.reportType);
  formData.append("content", payload.content);
  if (payload.conversationId) formData.append("conversation_id", payload.conversationId);
  if (payload.messageId) formData.append("message_id", payload.messageId);
  if (payload.clientContext) formData.append("client_context", JSON.stringify(payload.clientContext));
  if (payload.attachment) formData.append("attachment", payload.attachment);

  const res = await fetch(`${API_URL}/api/reports`, {
    method: "POST",
    headers: { ...getAuthHeaders() },
    body: formData,
  });
  const data = await res.json();
  if (!res.ok || data.status !== "success") {
    throw new Error(data.message || "Không gửi được báo cáo");
  }
  return data;
}

/* ── Conversations ───────────────────────────────── */

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_URL}/api/conversations`, {
    headers: { ...getAuthHeaders() },
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.conversations ?? [];
}

export async function fetchMessages(
  conversationId: string,
): Promise<Message[]> {
  try {
    const res = await fetch(
      `${API_URL}/api/conversations/${conversationId}/messages`,
      { headers: { ...getAuthHeaders() } }
    );
    if (!res.ok) {
      console.error("fetchMessages not ok:", res.status, res.statusText);
      return [];
    }
    const data = await res.json();
    return data.messages ?? [];
  } catch (err) {
    console.error("fetchMessages throw err:", err);
    return [];
  }
}

export async function deleteConversation(
  conversationId: string,
): Promise<void> {
  await fetch(`${API_URL}/api/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { ...getAuthHeaders() },
  });
}
