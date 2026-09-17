import { useCallback, useEffect, useState } from "react";
import { CalendarDays, RefreshCw } from "lucide-react";
import { api } from "../api";

type LocalEntry = { id: string; date: string; title: string; kind: "task" | "goal"; status: string };
type GoogleEntry = { id: string; title: string; start: string; end: string; location?: string };
type Entry = { id: string; day: string; title: string; source: string; detail: string; time?: string };

export function WorkCalendar({ mode, onError }: { mode: string; onError: (message: string) => void }) {
  const [local, setLocal] = useState<LocalEntry[]>([]);
  const [google, setGoogle] = useState<GoogleEntry[]>([]);
  const [window, setWindow] = useState<{ start: string; end: string } | null>(null);
  const [googleError, setGoogleError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const saved = await api<{ start: string; end: string; items: LocalEntry[] }>("/work/calendar?days=14");
      setLocal(saved.items);
      setWindow({ start: saved.start, end: saved.end });
      if (mode === "live") {
        try {
          const connected = await api<{ items: GoogleEntry[] }>("/apps/calendar");
          setGoogle(connected.items);
          setGoogleError("");
        } catch {
          setGoogle([]);
          setGoogleError("Google Calendar is unavailable. Your saved LIFEOS dates are still shown.");
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not load your calendar.");
    } finally { setLoading(false); }
  }, [mode, onError]);
  useEffect(() => { void load(); }, [load]);

  const entries: Entry[] = [
    ...local.map((item): Entry => ({ id: `local-${item.id}`, day: item.date, title: item.title,
      source: item.kind === "task" ? "Task due" : "Goal target", detail: item.status })),
    ...google.map((item): Entry => ({ id: `google-${item.id}`, day: item.start.slice(0, 10), title: item.title,
      source: "Google Calendar", detail: item.location || "", time: item.start.includes("T") ? item.start : undefined })),
  ].filter((item) => !!window && item.day >= window.start && item.day <= window.end)
    .sort((a, b) => a.day.localeCompare(b.day) || (a.time || "").localeCompare(b.time || "") || a.title.localeCompare(b.title));
  const groups = [...new Set(entries.map((item) => item.day))];

  return <section className="work-calendar" aria-label="Calendar agenda">
    <div className="work-toolbar"><div><h3>Next 14 days</h3><p>Task due dates, goal targets, and your connected Google Calendar.</p></div>
      <button className="button small" disabled={loading} onClick={() => void load()}><RefreshCw size={15} /> Refresh</button></div>
    {googleError && <p className="work-calendar-warning" role="status">{googleError}</p>}
    {loading && !window ? <div className="work-empty" role="status">Loading your calendar…</div> : !entries.length ?
      <div className="work-empty"><CalendarDays size={28} /><h4>No upcoming dates.</h4><p>Set a due date on a task or a target date on a goal to see it here.</p></div> :
      <div className="work-calendar-groups">{groups.map((day) => <section key={day} className="work-calendar-group">
        <h4>{new Date(`${day}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })}</h4>
        {entries.filter((item) => item.day === day).map((item) => <article key={item.id} className="work-calendar-entry">
          <span className="work-calendar-mark" /><div><strong>{item.title}</strong><p>{item.source}{item.time ? ` · ${new Date(item.time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : ""}{item.detail ? ` · ${item.detail}` : ""}</p></div>
        </article>)}</section>)}</div>}
  </section>;
}
