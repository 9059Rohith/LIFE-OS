import { useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  ArrowRight,
  CalendarDays,
  Check,
  ChevronDown,
  CircleAlert,
  ExternalLink,
  Hash,
  Inbox,
  LockKeyhole,
  MessageCircle,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from "lucide-react";
import { api, setCsrf } from "./api";
import type { Action, LifeEvent, Session } from "./types";
import "./desktop.css";

type DesktopProvider = "lifeos" | "discord" | "whatsapp";
type ViewStatus = "idle" | "loading" | "ready" | "error";
type ProviderStatus = { name: DesktopProvider; state: ViewStatus; detail: string };
type Bounds = { x: number; y: number; width: number; height: number };

declare global {
  interface Window {
    lifeosDesktop?: {
      select: (name: DesktopProvider) => void;
      setViewport: (bounds: Bounds) => void;
      reloadWorkspace: () => void;
      reload: (name: DesktopProvider) => void;
      onStatus: (handler: (status: ProviderStatus) => void) => () => void;
    };
  }
}

const providerInfo: Record<DesktopProvider, { title: string; description: string }> = {
  discord: { title: "Discord", description: "The actual Discord website" },
  whatsapp: { title: "WhatsApp", description: "The actual WhatsApp Web website" },
  lifeos: { title: "LIFEOS", description: "Plans, connections and account settings" },
};

function ProviderIcon({ name, size = 20 }: { name: DesktopProvider; size?: number }) {
  if (name === "discord") return <Hash size={size} aria-hidden="true" />;
  if (name === "whatsapp") return <MessageCircle size={size} aria-hidden="true" />;
  return <Waypoints size={size} aria-hidden="true" />;
}

function ActionIcon({ name }: { name: string }) {
  if (name === "gmail") return <Inbox size={17} aria-hidden="true" />;
  if (name === "calendar") return <CalendarDays size={17} aria-hidden="true" />;
  if (name === "discord") return <Hash size={17} aria-hidden="true" />;
  if (name === "whatsapp") return <MessageCircle size={17} aria-hidden="true" />;
  return <ExternalLink size={17} aria-hidden="true" />;
}

function humanStatus(status: string) {
  return status.replaceAll("_", " ");
}

function pageStatus(status: ViewStatus) {
  if (status === "ready") return "Page loaded";
  if (status === "loading") return "Loading page";
  if (status === "error") return "Load failed";
  return "Opening";
}

function actionState(action: Action) {
  if (action.status === "verified") return "verified";
  if (["failed", "uncertain", "blocked"].includes(action.status)) return "attention";
  if (["executing", "verifying", "running"].includes(action.status)) return "active";
  return "pending";
}

function DesktopApp() {
  const bridge = window.lifeosDesktop;
  const [selected, setSelected] = useState<DesktopProvider>("lifeos");
  const [statuses, setStatuses] = useState<Record<DesktopProvider, ProviderStatus>>({
    discord: { name: "discord", state: "idle", detail: "" },
    whatsapp: { name: "whatsapp", state: "idle", detail: "" },
    lifeos: { name: "lifeos", state: "idle", detail: "" },
  });
  const [session, setSession] = useState<Session | null>(null);
  const [events, setEvents] = useState<LifeEvent[]>([]);
  const [current, setCurrent] = useState<LifeEvent | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const stage = useRef<HTMLDivElement>(null);

  const select = useCallback((name: DesktopProvider) => {
    setSelected(name);
    bridge?.select(name);
  }, [bridge]);

  const load = useCallback(async () => {
    try {
      const authenticated = await api<Session>("/session");
      setCsrf(authenticated.csrf_token);
      setSession(authenticated);
      if (authenticated.mode !== "live") {
        setConnectionError("This desktop workspace requires a live LIFEOS account. Open LIFEOS to connect real services.");
        setEvents([]);
        setCurrent(null);
        return;
      }
      const list = await api<LifeEvent[]>("/events");
      setEvents(list);
      setCurrent((previous) => list.find((item) => item.id === previous?.id) || list[0] || null);
      setConnectionError("");
    } catch (cause) {
      setSession(null);
      setEvents([]);
      setCurrent(null);
      setConnectionError(cause instanceof Error ? cause.message : "LIFEOS is unavailable.");
    }
  }, []);

  useEffect(() => {
    if (!bridge) return;
    const unsubscribe = bridge.onStatus((next) => {
      setStatuses((previous) => ({ ...previous, [next.name]: next }));
    });
    bridge.select("lifeos");
    void load();
    return unsubscribe;
  }, [bridge, load]);

  useEffect(() => {
    if (!bridge) return;
    const element = stage.current;
    if (!element) return;
    const measure = () => {
      const box = element.getBoundingClientRect();
      bridge.setViewport({
        x: Math.round(box.left),
        y: Math.round(box.top),
        width: Math.round(box.width),
        height: Math.round(box.height),
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    window.addEventListener("resize", measure);
    measure();
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [bridge]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function createEvent() {
    const text = input.trim();
    if (!text || loading || session?.mode !== "live") return;
    setLoading(true);
    setError("");
    try {
      const event = await api<LifeEvent>("/events", "POST", { text, source: "text", simulation: false });
      setInput("");
      setCurrent(event);
      setExpanded(event.actions[0]?.id || null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The event could not be planned.");
    } finally {
      setLoading(false);
    }
  }

  async function operate(path: string, body: object = {}) {
    if (!current || loading) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<LifeEvent>(`/events/${current.id}/${path}`, "POST", body);
      setCurrent(updated);
      await load();
    } catch (cause) {
      await load();
      setError(cause instanceof Error ? cause.message : "The action could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  function focusAction(action: Action) {
    if (action.application === "discord" || action.application === "whatsapp") select(action.application);
    else select("lifeos");
  }

  const verified = current?.actions.filter((action) => action.status === "verified").length || 0;
  const total = current?.actions.length || 0;
  const pending = current?.actions.filter((action) => action.requires_approval && action.status === "awaiting_approval") || [];
  const approved = current?.actions.some((action) => action.status === "approved") || false;
  const uncertain = current?.actions.some((action) => action.status === "uncertain") || false;
  const active = current && ["executing", "verifying", "running"].includes(current.status);

  return (
    <div className="desktop-app">
      <aside className="desktop-rail" aria-label="Applications">
        <button className="desktop-brand" type="button" onClick={() => select("lifeos")} aria-label="Open LIFEOS">
          <Waypoints size={23} strokeWidth={2.2} aria-hidden="true" />
        </button>
        <div className="desktop-rail-divider" />
        {(["discord", "whatsapp", "lifeos"] as const).map((name) => (
          <button
            className={`desktop-rail-item ${selected === name ? "selected" : ""}`}
            type="button"
            key={name}
            onClick={() => select(name)}
            aria-label={`Open ${providerInfo[name].title}`}
            aria-pressed={selected === name}
            title={providerInfo[name].title}
          >
            <ProviderIcon name={name} />
            <span>{providerInfo[name].title}</span>
          </button>
        ))}
        <div className="desktop-rail-spacer" />
        <span className="desktop-rail-caption">LIFEOS</span>
      </aside>

      <main className="desktop-main">
        <header className="desktop-topbar">
          <div className="desktop-topbar-title">
            <span className="desktop-topbar-icon"><ProviderIcon name={selected} size={19} /></span>
            <div><strong>{providerInfo[selected].title}</strong><small>{providerInfo[selected].description}</small></div>
          </div>
          <div className="desktop-topbar-actions">
            <span className={`desktop-view-state ${statuses[selected].state}`} role="status">
              <i />{!bridge ? "Desktop only" : pageStatus(statuses[selected].state)}
            </span>
            <button type="button" onClick={() => bridge?.reload(selected)} aria-label={`Reload ${providerInfo[selected].title}`} title="Reload page">
              <RefreshCw size={17} aria-hidden="true" />
            </button>
          </div>
        </header>
        <div className="desktop-stage" ref={stage} aria-label={`${providerInfo[selected].title} application window`}>
          {!bridge && <div className="desktop-stage-fallback"><CircleAlert size={28} /><h2>Open the LIFEOS desktop app</h2><p>The signed-in provider pages appear here in the Windows application.</p></div>}
        </div>
        {statuses[selected].state === "error" && (
          <div className="desktop-provider-error" role="alert">
            <CircleAlert size={16} /> {statuses[selected].detail || `${providerInfo[selected].title} could not load.`}
          </div>
        )}
      </main>

      <aside className="desktop-dock" aria-label="LIFEOS ripple">
        <div className="desktop-dock-heading">
          <div className="desktop-dock-mark"><Waypoints size={18} /></div>
          <div><strong>Ripple</strong><span>Understand what changes next</span></div>
          <Sparkles size={17} className="desktop-dock-spark" aria-hidden="true" />
        </div>

        {!session || session.mode !== "live" ? (
          <div className="desktop-dock-empty">
            <LockKeyhole size={27} />
            <h2>Connect your workspace</h2>
            <p>Sign in to LIFEOS to plan changes with your real connected accounts.</p>
            <button type="button" className="desktop-primary" onClick={() => select("lifeos")}>Open LIFEOS <ArrowRight size={16} /></button>
            <button type="button" className="desktop-secondary" onClick={() => { setError(""); void load(); }}>Check again</button>
          </div>
        ) : (
          <>
            <form className="desktop-compose" onSubmit={(event) => { event.preventDefault(); void createEvent(); }}>
              <label htmlFor="desktop-event-input">What changed?</label>
              <textarea
                id="desktop-event-input"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Describe a real schedule change with its date and new time"
                rows={3}
                maxLength={4000}
              />
              <button type="submit" className="desktop-primary" disabled={!input.trim() || loading}>
                <Send size={15} />{loading ? "Working…" : "Plan impact"}
              </button>
            </form>

            {events.length > 0 && (
              <div className="desktop-event-picker">
                <label htmlFor="desktop-event-select">Recent events</label>
                <div className="desktop-select-wrap">
                  <select id="desktop-event-select" value={current?.id || ""} onChange={(event) => { setCurrent(events.find((item) => item.id === event.target.value) || null); setExpanded(null); }}>
                    {events.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                  </select>
                  <ChevronDown size={15} aria-hidden="true" />
                </div>
              </div>
            )}

            {!current ? (
              <div className="desktop-dock-empty desktop-dock-empty-event">
                <Waypoints size={30} />
                <h2>No ripples yet</h2>
                <p>When a real event arrives or you describe a change, its affected apps and approval steps appear here.</p>
              </div>
            ) : (
              <div className="desktop-event" aria-live="polite">
                <div className="desktop-event-summary">
                  <span className="desktop-kicker">{humanStatus(current.status)}</span>
                  <h2>{current.title}</h2>
                  <div className="desktop-source">
                    {current.source_ref
                      ? <><strong>Source</strong> {current.source_ref.application} · <code>{current.source_ref.record_id}</code></>
                      : <><strong>Source</strong> Entered in LIFEOS</>}
                  </div>
                  <p>{current.summary}</p>
                  <div className="desktop-progress-label"><span>Verified actions</span><strong>{verified} / {total}</strong></div>
                  <div className="desktop-progress" role="progressbar" aria-label="Verified actions" aria-valuenow={verified} aria-valuemin={0} aria-valuemax={total || 1}>
                    <span style={{ width: `${total ? (verified / total) * 100 : 0}%` }} />
                  </div>
                </div>
                {current.actions.length === 0 ? <p className="desktop-no-actions">No actions were proposed. Review the event details in LIFEOS.</p> : (
                  <ol className="desktop-action-list">
                    {current.actions.map((action) => (
                      <li key={action.id} className={`desktop-action ${actionState(action)}`}>
                        <button type="button" className="desktop-action-head" onClick={() => setExpanded(expanded === action.id ? null : action.id)} aria-expanded={expanded === action.id}>
                          <span className="desktop-action-icon"><ActionIcon name={action.application} /></span>
                          <span className="desktop-action-copy"><strong>{action.title}</strong><small>{humanStatus(action.status)}</small></span>
                          {action.status === "verified" ? <Check size={17} className="desktop-action-check" /> : <ChevronDown size={15} />}
                        </button>
                        {expanded === action.id && (
                          <div className="desktop-action-details">
                            <p>{action.reason}</p>
                            {action.target && <p><strong>Target</strong> {action.target}</p>}
                            {typeof action.arguments.body === "string" && <p className="desktop-action-body">{action.arguments.body}</p>}
                            {action.error && <p className="desktop-action-error" role="alert">{action.error}</p>}
                            {action.evidence?.verified === true && action.status === "verified" && (
                              <p className="desktop-action-evidence"><ShieldCheck size={14} /> Provider read-back verified</p>
                            )}
                            {action.evidence && action.evidence.verified !== true && (
                              <p className="desktop-action-error" role="alert">Provider read-back did not verify this action.</p>
                            )}
                            <div className="desktop-action-buttons">
                              <button type="button" onClick={() => focusAction(action)}>View app <ExternalLink size={13} /></button>
                              {action.status === "awaiting_approval" && <button type="button" disabled={loading} onClick={() => void operate("approve", { action_ids: [action.id], version: current.version })}>Approve this action</button>}
                            </div>
                          </div>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
                <div className="desktop-dock-controls">
                  {pending.length > 0 && <button type="button" className="desktop-secondary" disabled={loading} onClick={() => void operate("approve", { action_ids: pending.map((action) => action.id), version: current.version })}>Approve all ({pending.length})</button>}
                  {approved && !uncertain && !active && <button type="button" className="desktop-primary" disabled={loading} onClick={() => void operate("execute")}>Execute approved <ArrowRight size={15} /></button>}
                  <button type="button" className="desktop-link" onClick={() => select("lifeos")}>Open full plan <ExternalLink size={13} /></button>
                </div>
              </div>
            )}
          </>
        )}
        {(error || connectionError) && <div className="desktop-error" role="alert"><CircleAlert size={16} />{error || connectionError}</div>}
        <div className="desktop-dock-footer"><span><i /> {session?.mode === "live" ? "Live LIFEOS data" : "Not connected"}</span><span>Actions require approval</span></div>
      </aside>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<DesktopApp />);
