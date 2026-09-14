export type AppName =
  "gmail" | "calendar" | "discord" | "whatsapp" | "drive" | "maps";
export interface Action {
  id: string;
  application: AppName;
  type: string;
  title: string;
  reason: string;
  target: string;
  arguments: Record<string, unknown>;
  risk: string;
  status: string;
  requires_approval: boolean;
  reversible: boolean;
  dependencies: string[];
  evidence: Record<string, unknown> | null;
  compensation_status?: string;
  compensation_evidence?: Record<string, unknown>;
  compensation_error?: string;
  error: string | null;
  arguments_hash: string;
}
export interface TimelineItem {
  id: string;
  timestamp: string;
  stage: string;
  message: string;
  application?: string;
  latency_ms?: number;
}
export interface ContextItem {
  application: string;
  title: string;
  detail: string;
}
export interface LifeEvent {
  id: string;
  title: string;
  event_type: string;
  source: string;
  status: string;
  created_at: string;
  version: number;
  summary: string;
  limitations?: string[];
  simulation: boolean;
  entities: Record<string, unknown>;
  actions: Action[];
  context: ContextItem[];
  timeline: TimelineItem[];
}
export interface Session {
  user: { id: string; name: string };
  csrf_token: string;
  mode: string;
  voice_available: boolean;
}
export interface Integration {
  id: AppName;
  name: string;
  status: string;
  mode: string;
  description: string;
}
export interface AppRecords {
  application: AppName;
  records: Record<string, unknown>[];
}
export type Page =
  "overview" | "integrations" | "audit" | "settings" | "applications";
