/* ── Conversation ─────────────────────────────────── */

export interface Conversation {
  _id: string;
  session_id: string;
  user_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

/* ── Message ─────────────────────────────────────── */

export interface Message {
  _id: string;
  conversation_id: string;
  role: "user" | "assistant";
  question: string;
  normalized_question: string;
  answer: string;
  input_type: string;
  file_id: string | null;
  workflow_context: string;
  retrieved_chunk_ids: string[];
  router_label: string;
  created_at: string;
}

/* ── Chat request / response ─────────────────────── */

export interface ChatRequest {
  question: string;
  session_id: string;
  file?: File | null;
}

export interface ChatResponse {
  status: string;
  conversation_id: string;
  session_id: string;
  question: string;
  answer: string;
  router_label: string;
  input_type: string;
  retrieved_count: number;
  retrieved_chunks?: any[];
  message?: string;
}

/* ── UI state ────────────────────────────────────── */

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  routerLabel?: string;
  fileName?: string;
  timestamp: string;
  sources?: any[];
}

export type RouterLabel =
  | "PHAP_LY"
  | "THONG_SO"
  | "QUY_TRINH"
  | "HO_SO"
  | "VAN_HANH"
  | "XA_GIAO"
  | "KHONG_LIEN_QUAN"
  | "";
