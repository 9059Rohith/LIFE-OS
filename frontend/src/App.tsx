import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  ChevronRight,
  Command,
  House,
  Layers3,
  Link2,
  ListChecks,
  LoaderCircle,
  LogOut,
  Menu,
  Plane,
  Play,
  Plus,
  RotateCcw,
  SquareCheckBig,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, setCsrf, subscribeEvent } from "./api";
import type { Action, LifeEvent, Page, Session } from "./types";
import { Status, time, AppIcon } from "./components/Common";
import { Graph } from "./components/Graph";
import { WorkHub } from "./components/WorkHub";
import { ApprovalCenter } from "./components/ApprovalCenter";
import { ActionDialog } from "./components/ActionDialog";
import { VoiceCommand } from "./components/VoiceCommand";
import { WorkspacePages } from "./components/WorkspacePages";
import type { VoiceApproval } from "./voice";
export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [authNeeded, setAuthNeeded] = useState(false);
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [events, setEvents] = useState<LifeEvent[]>([]);
  const [event, setEvent] = useState<LifeEvent | null>(null);
  const [page, setPage] = useState<Page>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [review, setReview] = useState<Action | null>(null);
  const [menu, setMenu] = useState(false);
  const [starting, setStarting] = useState(true);
  const onError = useCallback((message: string) => setError(message), []);
  const refreshEvents = useCallback(async (focusId?: string) => {
    const next = await api<LifeEvent[]>("/events");
    setEvents(next);
    setEvent(
      (selected) =>
        next.find((item) => item.id === focusId) ||
        next.find((item) => item.id === selected?.id) ||
        next[0] ||
        null,
    );
  }, []);
  async function init() {
    try {
      const value = await api<Session>("/session");
      setSession(value);
      if (value.mode === "live") setPage(value.user.id === "owner" ? "applications" : "work");
      setCsrf(value.csrf_token);
      setAuthNeeded(false);
      if (value.mode === "demo" || value.user.id === "owner") await refreshEvents();
      else { setEvents([]); setEvent(null); }
    } catch {
      setAuthNeeded(true);
    } finally {
      setStarting(false);
    }
  }
  useEffect(() => {
    void init();
  }, []);
  useEffect(() => {
    if (!session || (session.mode === "live" && session.user.id !== "owner")) return;
    let active = true;
    const timer = setInterval(() => {
      void api<LifeEvent[]>("/events")
        .then((next) => {
          if (active) setEvents(next);
        })
        .catch(() => {});
    }, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [session]);
  useEffect(() => {
    if (!event?.id || (session?.mode === "live" && session.user.id !== "owner")) return;
    return subscribeEvent(event.id, () => {
      void api<LifeEvent>(`/events/${event.id}`)
        .then((next) => {
          setEvent(next);
          void refreshEvents();
        })
        .catch(() => {});
    });
  }, [event?.id, session, refreshEvents]);
  useEffect(() => {
    if (
      !event ||
      !["executing", "planning", "verifying", "running"].includes(event.status)
    )
      return;
    let active = true;
    const timer = setInterval(() => {
      void api<LifeEvent>(`/events/${event.id}`)
        .then((next) => {
          if (active) {
            setEvent(next);
            void refreshEvents();
          }
        })
        .catch((e) => {
          if (active)
            setError(
              e instanceof Error ? e.message : "Connection interrupted.",
            );
        });
    }, 900);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [event?.id, event?.status, refreshEvents]);
  async function perform(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "The request could not be completed. Check the connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function select(id: string) {
    await perform(async () => {
      setEvent(await api<LifeEvent>(`/events/${id}`));
      setPage("overview");
    });
  }
  async function demo(scenario = "flight") {
    await perform(async () => {
      const next = await api<LifeEvent>("/demo/run", "POST", { scenario });
      setEvent(next);
      setPage("overview");
      await refreshEvents(next.id);
    });
  }
  async function operation(op: string, ids?: string[]) {
    if (!event) return;
    await perform(async () => {
      try {
        if (op === "execute" || op === "retry")
          setEvent({ ...event, status: "executing" });
        const next = await api<LifeEvent>(
          `/events/${event.id}/${op}`,
          "POST",
          op === "approve" ? { action_ids: ids, version: event.version } : {},
        );
        setEvent(next);
        setReview(null);
        await refreshEvents(next.id);
      } catch (error) {
        setEvent(
          await api<LifeEvent>(`/events/${event.id}`).catch(() => event),
        );
        throw error;
      }
    });
  }
  async function reconcile(actionId: string) {
    if (!event) return;
    await perform(async () => {
      const next = await api<LifeEvent>(
        `/events/${event.id}/actions/${encodeURIComponent(actionId)}/reconcile`,
        "POST",
        {},
      );
      setEvent(next);
      await refreshEvents(next.id);
    });
  }
  async function changeAction(args: Record<string, unknown>) {
    if (!event || !review) return;
    await perform(async () => {
      await api(`/events/${event.id}/actions/${review.id}`, "PATCH", {
        arguments: args,
      });
      setEvent(await api<LifeEvent>(`/events/${event.id}`));
      setReview(null);
      await refreshEvents(event.id);
    });
  }
  async function reject() {
    if (!event || !review) return;
    await perform(async () => {
      await api(`/events/${event.id}/actions/${review.id}/reject`, "POST", {});
      setEvent(await api<LifeEvent>(`/events/${event.id}`));
      setReview(null);
      await refreshEvents(event.id);
    });
  }
  async function submit(text: string, simulation: boolean, source = "text") {
    await perform(async () => {
      const next = await api<LifeEvent>("/events", "POST", {
        text,
        simulation,
        source,
      });
      setEvent(next);
      setPage("overview");
      await refreshEvents(next.id);
    });
  }
  async function approveVoice(snapshot: VoiceApproval) {
    if (
      !event ||
      event.id !== snapshot.event_id ||
      event.version !== snapshot.version ||
      Date.now() - snapshot.captured_at > 120000
    ) {
      setError(
        "Voice approval expired or the plan changed. Review the current plan again.",
      );
      return;
    }
    await operation("approve", snapshot.action_ids);
  }
  async function executeVoice(snapshot: VoiceApproval) {
    if (
      !event ||
      event.id !== snapshot.event_id ||
      event.version !== snapshot.version ||
      Date.now() - snapshot.captured_at > 120000 ||
      !event.actions.some((a) => a.status === "approved")
    ) {
      setError(
        "Voice execution requires a current approved plan. Review and approve the actions first.",
      );
      return;
    }
    await operation("execute");
  }
  async function reset() {
    await perform(async () => {
      await api("/demo/reset", "POST", {});
      setEvent(null);
      await refreshEvents();
    });
  }
  async function login() {
    await perform(async () => {
      await api("/auth/login", "POST", { password, ...(username.trim() ? { username: username.trim() } : {}) });
      setPassword("");
      setUsername("");
      await init();
    });
  }
  const primaryNavigation: [Page, typeof House, string][] = [
    ["overview", House, "Overview"],
    ["work", SquareCheckBig, "My work"],
    ["integrations", Link2, "Integrations"],
    ["audit", ListChecks, "Audit trail"],
    ["applications", Layers3, session?.mode === "demo" ? "Demo applications" : "Connected apps"],
    ["settings", Settings, "Settings"],
  ];
  const navigation = session?.mode === "live" && session.user.id !== "owner"
    ? primaryNavigation.filter(([key]) => key === "work" || key === "settings")
    : primaryNavigation;
  const pageHeading: Record<Page, [string, string]> = {
    overview: ["Something changed. You’re in control.", "Understand the impact. Approve the next move."],
    work: ["Your work, connected.", "A clear view of what matters and what happened."],
    integrations: ["Your connections.", "Review access to the services you choose."],
    applications: ["Your apps, in context.", "See the source behind each LIFEOS action."],
    audit: ["Every decision, traceable.", "Follow approvals, attempts and provider receipts."],
    settings: ["Your workspace, your rules.", "Control preferences, access and local data."],
  };
  if (starting)
    return (
      <div className="boot-screen">
        <span className="brand">
          LIFEOS
          <span />
        </span>
        <LoaderCircle className="spin" />
        <p>Opening your workspace…</p>
      </div>
    );
  if (authNeeded)
    return (
      <div className="login-screen">
        <form
          className="panel login-card"
          onSubmit={(e) => {
            e.preventDefault();
            void login();
          }}
        >
          <span className="brand">
            LIFEOS
            <span />
          </span>
          <h1>
            Your digital life,
            <br />
            in perspective.
          </h1>
          <p>Sign in to your private operations workspace.</p>
          <label htmlFor="username">Username <span className="field-note">(leave blank for the primary workspace)</span></label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <label htmlFor="password">Workspace password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button className="button primary" disabled={busy}>
            Open workspace
            <ArrowRight size={17} />
          </button>
          {error && (
            <p className="inline-error" role="alert">
              {error}
            </p>
          )}
          <p className="field-note">
            Having trouble connecting? Check your connection and refresh this
            page.
          </p>
        </form>
      </div>
    );
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "is-open" : ""}`}>
        <a
          className="brand"
          href="#overview"
          onClick={() => setPage(session?.mode === "live" && session.user.id !== "owner" ? "work" : "overview")}
        >
          LIFEOS
          <span />
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav>
          {navigation.map(([key, Icon, label]) => (
              <button
                key={key}
                className={page === key ? "active" : ""}
                onClick={() => {
                  setPage(key);
                  setMenu(false);
                }}
              >
                <Icon size={18} />
                <span>{label}</span>
                {page === key && <i />}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="safe-note">
            <ShieldCheck size={20} />
            <strong>Built around your trust.</strong>
            <p>
              Every action is visible.
              <br />
              Every decision is yours.
            </p>
          </div>
          <button className="profile" onClick={() => setPage("settings")}>
            <span className="avatar">
              {session?.user.name?.charAt(0) || "D"}
            </span>
            <span>
              <strong>
                {session?.mode === "demo"
                  ? "Demo workspace"
                  : session?.user.name}
              </strong>
              <small>
                {session?.mode === "demo"
                  ? "Local simulated applications"
                  : "Private workspace"}
              </small>
            </span>
            <ChevronRight size={14} />
          </button>
          {session?.mode !== "demo" && (
            <button
              className="logout"
              onClick={() =>
                void perform(async () => {
                  await api("/auth/logout", "POST", {});
                  setSession(null);
                  setEvents([]);
                  setEvent(null);
                  setPage("overview");
                  setAuthNeeded(true);
                })
              }
            >
              <LogOut size={14} />
              Sign out
            </button>
          )}
        </div>
      </aside>
      <main>
        <header className="main-header">
          <div className="heading-group">
            <button
              className="icon-button mobile-menu"
              aria-label="Toggle navigation"
              onClick={() => setMenu(!menu)}
            >
              <Menu size={21} />
            </button>
            <div>
              <h1>{pageHeading[page][0]}</h1>
              <p>{pageHeading[page][1]}</p>
            </div>
          </div>
          <div className="header-actions">
            <div className="workspace-indicator">
              <i />
              <span>
                {session?.mode === "demo" ? "Demo workspace" : "Live workspace"}
                <small>
                  {session?.mode === "demo"
                    ? "Local simulated applications"
                    : "Approval protected"}
                </small>
              </span>
            </div>
            {session?.mode === "demo" && (
              <button
                className="button primary hero-button"
                disabled={busy}
                onClick={() => void demo()}
              >
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Play size={15} />
                )}
                Run hero demo
              </button>
            )}
          </div>
        </header>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button
              className="icon-button"
              aria-label="Dismiss error"
              onClick={() => setError("")}
            >
              <X size={17} />
            </button>
          </div>
        )}
        {page === "overview" ? (
          <>
            {!!event?.limitations?.length && (
              <div className="notice" role="status">
                <ShieldCheck size={18} />
                <span>{event.limitations.join(" ")}</span>
              </div>
            )}
            <div className="overview-grid">
              <section className="panel event-feed">
                <div className="panel-heading">
                  <h2>Recent events</h2>
                  <span className="count">{events.length}</span>
                </div>
                <div className="feed-items">
                  {events.map((item) => (
                    <button
                      key={item.id}
                      className={`event-item ${event?.id === item.id ? "selected" : ""}`}
                      onClick={() => void select(item.id)}
                    >
                      <span className="feed-icon">
                        {item.event_type?.includes("flight") ? (
                          <Plane size={20} />
                        ) : (
                          <CalendarDays size={20} />
                        )}
                      </span>
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.source} · {time(item.created_at)}
                        </small>
                        <Status value={item.status} />
                      </span>
                      <ChevronRight size={14} />
                    </button>
                  ))}
                  {!events.length && (
                    <div className="feed-empty">
                      <div className="feed-empty-icon">
                        <Activity size={24} />
                      </div>
                      <h3>
                        A little change.
                        <br />A bigger picture.
                      </h3>
                      <p>Your events and their impact will appear here.</p>
                    </div>
                  )}
                </div>
                {session?.mode === "demo" && (
                  <div className="scenario-picker">
                    <small>EXPLORE A SCENARIO</small>
                    <button onClick={() => void demo("flight")} disabled={busy}>
                      <Plane size={17} />
                      <span>
                        Flight disruption<small>Gmail → connected applications</small>
                      </span>
                      <ArrowUpRight size={15} />
                    </button>
                    <button
                      onClick={() => void demo("meeting")}
                      disabled={busy}
                    >
                      <CalendarDays size={17} />
                      <span>
                        Meeting rescheduled
                        <small>Discord → connected context</small>
                      </span>
                      <ArrowUpRight size={15} />
                    </button>
                    <button
                      className="reset-demo"
                      onClick={() => void reset()}
                      disabled={busy}
                    >
                      <RotateCcw size={13} />
                      Reset demo
                    </button>
                  </div>
                )}
                <div className="feed-footer">
                  <Command size={13} />
                  <span>Start with “Something changed.”</span>
                </div>
              </section>
              <Graph event={event} onSelect={setReview} />
              <section className="panel timeline-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Activity timeline</h2>
                    <p>
                      {event
                        ? new Date(event.created_at).toLocaleDateString(
                            undefined,
                            { month: "long", day: "numeric" },
                          )
                        : "From first signal to final check."}
                    </p>
                  </div>
                  <Activity size={17} />
                </div>
                {event ? (
                  <>
                    <div className="timeline">
                      {(event.timeline || []).map((item, i) => (
                        <div className="timeline-item" key={item.id || i}>
                          <i
                            className={
                              i === event.timeline.length - 1 ? "last" : ""
                            }
                          />
                          <small>
                            {time(item.timestamp)}
                            {typeof item.latency_ms === "number"
                              ? ` · ${Math.round(item.latency_ms)} ms`
                              : ""}
                          </small>
                          <strong>{item.stage.replaceAll("_", " ")}</strong>
                          <p>{item.message}</p>
                        </div>
                      ))}
                    </div>
                    <div className="timeline-status">
                      <Status value={event.status} />
                    </div>
                  </>
                ) : (
                  <div className="timeline-empty">
                    <div className="quiet-timeline">
                      <i />
                      <span />
                      <i />
                      <span />
                      <i />
                    </div>
                    <p>
                      Follow the reasoning.
                      <br />
                      See the work happen.
                    </p>
                    <small>Real steps, measured as they happen.</small>
                  </div>
                )}
              </section>
              <div className="approval-slot">
                {event &&
                  ["blocked", "clarification_required"].includes(
                    event.status,
                  ) && (
                    <div className="plan-notice" role="alert">
                      <Status value={event.status} />
                      <p>{event.summary}</p>
                    </div>
                  )}
                <ApprovalCenter
                  event={event}
                  busy={busy}
                  onAction={(op, ids) => void operation(op, ids)}
                  onReview={setReview}
                  onReconcile={(id) => void reconcile(id)}
                />
              </div>
            </div>
            {event && (
              <section className="context-strip">
                <div>
                  <Link2 size={14} />
                  <strong>Context behind the plan</strong>
                </div>
                <div>
                  {event.context?.map((item, i) => (
                    <details key={i}>
                      <summary>
                        <AppIcon name={item.application} size={13} />
                        {item.title}
                        <Plus size={11} />
                      </summary>
                      <p>{item.detail}</p>
                    </details>
                  ))}
                </div>
              </section>
            )}
            <VoiceCommand
              busy={busy}
              voiceAvailable={session?.voice_available || false}
              summary={event?.summary}
              onSubmit={submit}
              onError={onError}
              approvalContext={
                event && !event.simulation
                  ? {
                      event_id: event.id,
                      version: event.version,
                      action_ids: event.actions
                        .filter(
                          (a) =>
                            a.requires_approval &&
                            a.status === "awaiting_approval",
                        )
                        .map((a) => a.id),
                      captured_at: Date.now(),
                    }
                  : undefined
              }
              onVoiceApproval={approveVoice}
              onVoiceExecute={executeVoice}
            />
          </>
        ) : page === "work" ? (
          <WorkHub onError={onError} mode={session?.mode || "demo"} />
        ) : (
          <WorkspacePages
            page={page}
            onError={onError}
            mode={session?.mode || "demo"}
            onOpenPlan={(plan) => {
              setEvent(plan);
              setPage("overview");
              void refreshEvents();
            }}
          />
        )}
        <footer className="main-footer">
          <span>Something changed. LIFEOS handles what happens next.</span>
          <span>
            <ShieldCheck size={12} />
            Human-approved. Independently verified.
          </span>
        </footer>
      </main>
      {review && (
        <ActionDialog
          key={review.id}
          action={review}
          readOnly={
            !event ||
            event.simulation ||
            [
              "cancelled",
              "compensated",
              "resolved",
              "blocked",
              "clarification_required",
            ].includes(event.status)
          }
          busy={busy}
          onClose={() => setReview(null)}
          onSave={changeAction}
          onReject={reject}
          onApprove={() => operation("approve", [review.id])}
        />
      )}
    </div>
  );
}
