import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api } from "../api";
import { WorkCalendar } from "./WorkCalendar";

type Collection = "tasks" | "projects" | "goals" | "habits" | "notes";
type WorkItem = {
  id: string; title: string; description?: string; body?: string;
  status?: string; priority?: string; due_date?: string | null;
  target_date?: string | null; project_id?: string | null;
  goal_id?: string | null; task_id?: string | null;
  frequency?: string; target_per_week?: number; archived?: boolean;
  checkins?: string[]; streak?: number; created_at: string;
};
type PageResult = { items: WorkItem[]; total: number; offset: number; limit: number };
type Summary = {
  projects: number; goals: number; tasks: number; tasks_completed: number;
  tasks_due_today: number; habits: number; notes: number; checkins: number;
  goal_progress: { id: string; completed: number; total: number }[];
  project_progress: { id: string; completed: number; total: number }[];
  habit_streaks: { id: string; streak: number }[];
  activity_days: { day: string; count: number }[];
};
type Notice = { id: string; category: "task_due" | "task_overdue" | "habit_due"; item_id: string; title: string; date: string };
type LinkOption = { id: string; title: string };
type Dashboard = { page: PageResult; summary: Summary; links: Record<string, LinkOption[]>; timezone: string; notifications: Notice[] };
type Draft = {
  title: string; description: string; body: string; status: string; priority: string;
  due_date: string; target_date: string; project_id: string; goal_id: string;
  task_id: string; frequency: string; target_per_week: number; archived: boolean;
};
const tabs: { id: Collection; label: string; empty: string }[] = [
  { id: "tasks", label: "Tasks", empty: "No tasks yet. Capture the next thing you need to do." },
  { id: "projects", label: "Projects", empty: "No projects yet. Create a space for related work." },
  { id: "goals", label: "Goals", empty: "No goals yet. Give your work a destination." },
  { id: "habits", label: "Habits", empty: "No habits yet. Start with one action to repeat." },
  { id: "notes", label: "Notes", empty: "No notes yet. Save a thought or reference." },
];
const blank: Draft = {
  title: "", description: "", body: "", status: "", priority: "medium", due_date: "",
  target_date: "", project_id: "", goal_id: "", task_id: "", frequency: "daily",
  target_per_week: 1, archived: false,
};
const pageSize = 20;
const todayIn = (timezone: string) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const value = (type: string) => parts.find((part) => part.type === type)!.value;
  return `${value("year")}-${value("month")}-${value("day")}`;
};

function payloadFor(collection: Collection, draft: Draft) {
  const shared = { title: draft.title.trim() };
  if (collection === "notes") return {
    ...shared, body: draft.body.trim(), project_id: draft.project_id || null,
    goal_id: draft.goal_id || null, task_id: draft.task_id || null,
  };
  const named = { ...shared, description: draft.description.trim() };
  if (collection === "projects") return { ...named, status: draft.status || "active" };
  if (collection === "goals") return {
    ...named, status: draft.status || "active", target_date: draft.target_date || null,
    project_id: draft.project_id || null,
  };
  if (collection === "tasks") return {
    ...named, status: draft.status || "todo", priority: draft.priority,
    due_date: draft.due_date || null, project_id: draft.project_id || null,
    goal_id: draft.goal_id || null,
  };
  return {
    ...named, frequency: draft.frequency, target_per_week: Number(draft.target_per_week),
    archived: draft.archived, project_id: draft.project_id || null,
    goal_id: draft.goal_id || null,
  };
}

export function WorkHub({ onError, mode }: { onError: (message: string) => void; mode: string }) {
  const [collection, setCollection] = useState<Collection>("tasks");
  const [calendar, setCalendar] = useState(false);
  const [offset, setOffset] = useState(0);
  const [records, setRecords] = useState<PageResult | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [links, setLinks] = useState<Record<string, LinkOption[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editor, setEditor] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [notice, setNotice] = useState("");
  const [notifications, setNotifications] = useState<Notice[]>([]);
  const [timezone, setTimezone] = useState("UTC");
  const loadGeneration = useRef(0);

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    setLoading(true);
    try {
      const dashboard = await api<Dashboard>(`/work/dashboard?collection=${collection}&offset=${offset}&limit=${pageSize}`);
      if (generation !== loadGeneration.current) return;
      setRecords(dashboard.page);
      setSummary(dashboard.summary);
      setLinks(dashboard.links);
      setTimezone(dashboard.timezone);
      setNotifications(dashboard.notifications);
    } catch (error) {
      if (generation === loadGeneration.current)
        onError(error instanceof Error ? error.message : "Could not load your work.");
    } finally {
      if (generation === loadGeneration.current) setLoading(false);
    }
  }, [collection, offset, onError]);
  useEffect(() => { void load(); return () => { loadGeneration.current += 1; }; }, [load]);

  function switchTab(next: Collection) {
    setCollection(next); setCalendar(false); setOffset(0); setEditor(null); setNotice("");
  }
  function edit(item?: WorkItem) {
    setEditor(item?.id || "new");
    setDraft(item ? {
      title: item.title, description: item.description || "", body: item.body || "",
      status: item.status || "", priority: item.priority || "medium",
      due_date: item.due_date || "", target_date: item.target_date || "",
      project_id: item.project_id || "", goal_id: item.goal_id || "",
      task_id: item.task_id || "", frequency: item.frequency || "daily",
      target_per_week: item.target_per_week || 1, archived: item.archived || false,
    } : { ...blank });
    setNotice("");
  }
  function change<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor) return;
    setSaving(true);
    try {
      await api(`/work/${collection}${editor === "new" ? "" : `/${editor}`}`,
        editor === "new" ? "POST" : "PATCH", payloadFor(collection, draft));
      setEditor(null);
      setNotice(`${collection.slice(0, -1)} saved.`);
      await load();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not save this item.");
    } finally { setSaving(false); }
  }
  async function remove(item: WorkItem) {
    if (!window.confirm(`Delete “${item.title}”? This cannot be undone.`)) return;
    setSaving(true);
    try {
      await api(`/work/${collection}/${item.id}`, "DELETE");
      setNotice(`${collection.slice(0, -1)} deleted.`);
      if (records?.items.length === 1 && offset > 0) setOffset(offset - pageSize);
      else await load();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not delete this item.");
    } finally { setSaving(false); }
  }
  async function setTaskStatus(item: WorkItem) {
    setSaving(true);
    try {
      await api(`/work/tasks/${item.id}`, "PATCH", { status: item.status === "done" ? "todo" : "done" });
      await load();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not update the task.");
    } finally { setSaving(false); }
  }
  async function checkHabit(item: WorkItem) {
    setSaving(true);
    const day = todayIn(timezone);
    try {
      if (item.checkins?.includes(day)) await api(`/work/habits/${item.id}/checkins/${day}`, "DELETE");
      else await api(`/work/habits/${item.id}/checkins`, "POST", { day });
      await load();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not update the habit.");
    } finally { setSaving(false); }
  }
  async function dismiss(notification: Notice) {
    try {
      await api(`/work/notifications/${notification.id}/dismiss`, "POST", {});
      setNotifications((current) => current.filter((item) => item.id !== notification.id));
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not dismiss the reminder.");
    }
  }
  const label = tabs.find((tab) => tab.id === collection)!;
  const name = (group: string, id?: string | null) => links[group]?.find((item) => item.id === id)?.title;
  return <section className="work-hub" aria-label="My work">
    <header className="work-header">
      <div><span className="work-eyebrow">YOUR WORKSPACE</span><h2>Make progress visible.</h2>
        <p>Plan your work, connect it to goals, and record what actually happened.</p></div>
      <button className="button small" onClick={() => void load()} disabled={loading}><RefreshCw size={15} /> Refresh</button>
    </header>
    <div className="work-metrics" aria-label="Work summary">
      {[{ label: "Open tasks", value: summary ? summary.tasks - summary.tasks_completed : null },
        { label: "Completed tasks", value: summary?.tasks_completed },
        { label: "Due today", value: summary?.tasks_due_today },
        { label: "Habit check-ins", value: summary?.checkins }].map((metric) =>
        <div className="work-metric" key={metric.label}><span>{metric.label}</span><strong>{metric.value ?? "—"}</strong></div>)}
    </div>
    <div className="work-activity" aria-label="Activity from saved work history">
      <div><strong>Activity</strong><span>Last 14 days · saved changes and check-ins</span></div>
      {summary?.activity_days.some((day) => day.count > 0) ?
        <div className="work-activity-bars">{summary.activity_days.map((day) =>
          <div key={day.day} className="work-activity-day" title={`${day.day}: ${day.count} activities`}>
            <i style={{ height: `${Math.max(4, day.count / Math.max(1, ...summary.activity_days.map((value) => value.count)) * 100)}%` }} />
          </div>)}</div> : <p>No activity recorded yet.</p>}
    </div>
    {!!notifications.length && <section className="work-reminders" aria-label="Reminders from saved work">
      <div><strong>Needs your attention</strong><span>{notifications.length} {notifications.length === 1 ? "reminder" : "reminders"} from your tasks and habits</span></div>
      <div className="work-reminder-list">{notifications.map((item) => <article key={item.id} className="work-reminder">
        <div><strong>{item.title}</strong><span>{item.category === "task_overdue" ? `Overdue since ${item.date}` : item.category === "task_due" ? "Due today" : "Habit check-in due today"}</span></div>
        <button className="work-text-button" onClick={() => void dismiss(item)} aria-label={`Dismiss reminder for ${item.title}`}>Dismiss</button>
      </article>)}</div>
    </section>}
    <div className="work-tabs" role="tablist" aria-label="Work collections" onKeyDown={(event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=tab]")];
      const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
      if (current < 0) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next].focus(); buttons[next].click();
    }}>
      {tabs.map((tab) => <button key={tab.id} role="tab" disabled={saving} aria-selected={!calendar && collection === tab.id}
        className={!calendar && collection === tab.id ? "selected" : ""} onClick={() => switchTab(tab.id)}>{tab.label}
        <span>{summary?.[tab.id] ?? "—"}</span></button>)}
      <button role="tab" disabled={saving} aria-selected={calendar} className={calendar ? "selected" : ""}
        onClick={() => { setCalendar(true); setEditor(null); setNotice(""); }}>Calendar</button>
    </div>
    {calendar ? <WorkCalendar mode={mode} onError={onError} /> : <>
    <div className="work-toolbar"><div><h3>{label.label}</h3><p>{records?.total ?? 0} saved</p></div>
      <button className="button primary small" onClick={() => edit()} disabled={loading}><Plus size={15} /> New {collection.slice(0, -1)}</button></div>
    {notice && <p className="work-notice" role="status">{notice}</p>}
    {editor && <form className="work-editor" onSubmit={(event) => void save(event)}>
      <div className="work-editor-heading"><h4>{editor === "new" ? "New" : "Edit"} {collection.slice(0, -1)}</h4>
        <button type="button" className="work-text-button" onClick={() => setEditor(null)}>Close</button></div>
      <div className="work-form-grid">
        <label>Title<input required maxLength={160} autoFocus value={draft.title} onChange={(event) => change("title", event.target.value)} /></label>
        {collection !== "notes" && <label className="work-wide">Description<textarea maxLength={4000} rows={3} value={draft.description} onChange={(event) => change("description", event.target.value)} /></label>}
        {collection === "notes" && <label className="work-wide">Note<textarea required maxLength={20000} rows={7} value={draft.body} onChange={(event) => change("body", event.target.value)} /></label>}
        {(["projects", "goals", "tasks"] as Collection[]).includes(collection) && <label>Status<select value={draft.status || (collection === "tasks" ? "todo" : "active")} onChange={(event) => change("status", event.target.value)}>
          {(collection === "tasks" ? ["todo", "doing", "done"] : ["active", "completed", "archived"]).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>}
        {collection === "tasks" && <><label>Priority<select value={draft.priority} onChange={(event) => change("priority", event.target.value)}>
          {["low", "medium", "high"].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Due date<input type="date" value={draft.due_date} onChange={(event) => change("due_date", event.target.value)} /></label></>}
        {collection === "goals" && <label>Target date<input type="date" value={draft.target_date} onChange={(event) => change("target_date", event.target.value)} /></label>}
        {collection === "habits" && <><label>Frequency<select value={draft.frequency} onChange={(event) => change("frequency", event.target.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option></select></label>
          <label>Target per week<input type="number" min={1} max={7} value={draft.target_per_week} onChange={(event) => change("target_per_week", Number(event.target.value))} /></label>
          <label className="work-checkbox"><input type="checkbox" checked={draft.archived} onChange={(event) => change("archived", event.target.checked)} /> Archived</label></>}
        {collection !== "projects" && <label>Project<select value={draft.project_id} onChange={(event) => change("project_id", event.target.value)}><option value="">No project</option>{links.projects?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>}
        {(["tasks", "habits", "notes"] as Collection[]).includes(collection) && <label>Goal<select value={draft.goal_id} onChange={(event) => change("goal_id", event.target.value)}><option value="">No goal</option>{links.goals?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>}
        {collection === "notes" && <label>Task<select value={draft.task_id} onChange={(event) => change("task_id", event.target.value)}><option value="">No task</option>{links.tasks?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>}
      </div>
      <div className="work-editor-actions"><button type="button" className="button small" onClick={() => setEditor(null)}>Cancel</button><button className="button primary small" disabled={saving}>{saving ? "Saving…" : "Save"}</button></div>
    </form>}
    {loading ? <div className="work-empty" role="status">Loading your work…</div> : !records?.items.length ?
      <div className="work-empty"><span>✦</span><h4>Your {label.label.toLowerCase()} start here.</h4><p>{label.empty}</p></div> :
      <div className="work-list">{records.items.map((item) => {
        const progress = collection === "projects" ? summary?.project_progress.find((entry) => entry.id === item.id)
          : collection === "goals" ? summary?.goal_progress.find((entry) => entry.id === item.id) : undefined;
        return <article className="work-row" key={item.id}>
          <div className="work-row-main">
            {collection === "tasks" && <button className={`work-complete ${item.status === "done" ? "done" : ""}`} disabled={saving} aria-label={`${item.status === "done" ? "Reopen" : "Complete"} ${item.title}`} onClick={() => void setTaskStatus(item)}>{item.status === "done" && <Check size={13} />}</button>}
            <div><h4>{item.title}</h4><p>{collection === "notes" ? item.body : item.description || ""}</p>
              <div className="work-row-meta">
                {item.status && <span>{item.status}</span>}{item.priority && <span>{item.priority} priority</span>}
                {item.due_date && <span>Due {item.due_date}</span>}{item.target_date && <span>Target {item.target_date}</span>}
                {item.project_id && <span>{name("projects", item.project_id) || "Linked project"}</span>}
                {item.goal_id && <span>{name("goals", item.goal_id) || "Linked goal"}</span>}
                {item.task_id && <span>{name("tasks", item.task_id) || "Linked task"}</span>}
                {progress && <span>{progress.completed}/{progress.total} tasks done</span>}
                {collection === "habits" && <span>{item.streak || 0} {item.frequency === "weekly" ? "week" : "day"} streak</span>}
              </div></div>
          </div>
          <div className="work-row-actions">
            {collection === "habits" && !item.archived && <button className="button small" disabled={saving} onClick={() => void checkHabit(item)}>{item.checkins?.includes(todayIn(timezone)) ? "Undo today" : "Check in"}</button>}
            <button className="work-text-button" onClick={() => edit(item)}>Edit</button>
            <button className="work-icon-button" aria-label={`Delete ${item.title}`} disabled={saving} onClick={() => void remove(item)}><Trash2 size={16} /></button>
          </div>
        </article>;
      })}</div>}
    {!loading && !!records?.total && <div className="work-pagination"><span>Showing {offset + 1}–{Math.min(offset + pageSize, records.total)} of {records.total}</span>
      <div><button className="work-icon-button" aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - pageSize))}><ArrowLeft size={16} /></button>
        <button className="work-icon-button" aria-label="Next page" disabled={offset + pageSize >= records.total || loading} onClick={() => setOffset(offset + pageSize)}><ArrowRight size={16} /></button></div></div>}
    </>}
  </section>;
}
