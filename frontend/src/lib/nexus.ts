// Espelho manual dos modelos Pydantic (backend/models/nexus.py) — mantenha em sincronia.
// Nada infere entre Python e TypeScript: este par é disciplina manual.
import { apiGet, apiPost } from "@/lib/api";

export interface WeatherContext {
  city?: string;
  temperature?: number;
  apparent?: number;
  humidity?: number;
  wind_kmh?: number;
  condition?: string;
  temp_min?: number;
  temp_max?: number;
  rain_prob?: number;
}

export interface FinanceEntry {
  bid?: number;
  pct?: number;
}

export interface FinanceContext {
  usd?: FinanceEntry;
  eur?: FinanceEntry;
  btc?: FinanceEntry;
}

export interface NewsItem {
  title: string;
  source: string;
  link: string;
  published: string;
}

export interface BriefingContext {
  weather?: WeatherContext | null;
  finance?: FinanceContext | null;
  news?: Record<string, NewsItem[]>;
  collected_at?: string;
}

export interface BriefingCard {
  type: "clima" | "agenda" | "emails" | "noticias" | "saude" | string;
  title: string;
  content: string;
}

export interface BriefingResponse {
  id: string;
  created_at: string;
  speech: string;
  full_text: string;
  cards: BriefingCard[];
  face_verified: boolean;
  source: "gemini" | "local" | string;
  context: BriefingContext;
}

export interface FaceVerifyResponse {
  verified: boolean;
  detail: string;
}

export interface ChatResponse {
  id: string;
  created_at: string;
  reply: string;
  cards: BriefingCard[];
  source: "gemini" | "local" | string;
}

export interface MemoryEvent {
  id: string;
  kind: "briefing" | "user" | "nexus" | string;
  text: string;
  created_at: string;
  source?: string | null;
  cards: BriefingCard[];
}

/* ── Chamadas tipadas pela camada /api ─────────────────────────────── */

export const runBriefing = (faceVerified: boolean) =>
  apiPost<BriefingResponse>("/briefing", { face_verified: faceVerified });

export const fetchLatestBriefing = () => apiGet<BriefingResponse | null>("/briefing/latest");

export const verifyFace = (image: string) => apiPost<FaceVerifyResponse>("/face-verify", { image });

export const sendChatMessage = (message: string) => apiPost<ChatResponse>("/chat", { message });

export const fetchMemory = (limit = 60) => apiGet<MemoryEvent[]>(`/memory?limit=${limit}`);