import {
  CalendarDays,
  Mail,
  MessageCircle,
  MessagesSquare,
  FileText,
  MapPin,
  Plane,
  Check,
  Clock3,
  ShieldAlert,
  LoaderCircle,
} from "lucide-react";
import type { AppName } from "../types";
export const appNames: Record<AppName, string> = {
  gmail: "Gmail",
  calendar: "Calendar",
  whatsapp: "WhatsApp",
  discord: "Discord",
  drive: "Drive",
  maps: "Maps",
};
const icons = {
  gmail: Mail,
  calendar: CalendarDays,
  whatsapp: MessageCircle,
  discord: MessagesSquare,
  drive: FileText,
  maps: MapPin,
};
export function AppIcon({ name, size = 19 }: { name: string; size?: number }) {
  const Icon = icons[name as AppName] || Plane;
  return <Icon size={size} aria-hidden="true" />;
}
export function Status({ value }: { value: string }) {
  const v = value.toLowerCase();
  const ok = [
    "verified",
    "read_access_verified",
    "resolved",
    "completed",
    "connected",
    "approved",
  ].includes(v);
  const bad = [
    "failed",
    "blocked",
    "rejected",
    "cancelled",
    "needs_attention",
    "needs_human",
    "partial",
    "partial_failure",
    "uncertain",
    "blocked_dependency",
    "clarification_required",
  ].includes(v);
  const busy = ["executing", "verifying", "planning", "running"].includes(v);
  const Icon = ok ? Check : bad ? ShieldAlert : busy ? LoaderCircle : Clock3;
  return (
    <span
      className={`status ${ok ? "good" : bad ? "bad" : busy ? "busy" : "pending"}`}
    >
      <Icon size={12} className={busy ? "spin" : ""} />
      {value.replaceAll("_", " ")}
    </span>
  );
}
export function display(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
export function time(value: string) {
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
