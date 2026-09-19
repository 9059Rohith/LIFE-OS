import { useCallback, useEffect, useRef, useState } from "react";
import { Hash, Inbox, LockKeyhole, RefreshCw, Waypoints } from "lucide-react";
import { api } from "../api";
import type { AppName, Integration, LifeEvent } from "../types";
import { AppIcon, appNames, Status } from "./Common";

type Item = {
  id: string;
  from?: string;
  to?: string;
  subject?: string;
  preview?: string;
  date?: string;
  unread?: boolean;
  author?: string;
  avatar_url?: string;
  content?: string;
  attachments?: number;
  title?: string;
  start?: string;
  end?: string;
  etag?: string;
  location?: string;
  name?: string;
  type?: string;
  modified?: string;
  outgoing?: boolean;
  status?: string;
};
type Screen = { application: AppName; title: string; items: Item[]; message?: string; status?: string };
type MailDetail = { id: string; from: string; to: string; subject: string; date: string; body: string };
type PanelState = { screen: Screen | null; loading: boolean; error: string };
const apps: AppName[] = ["discord", "gmail", "whatsapp", "calendar", "drive"];
const initialPanels = Object.fromEntries(apps.map((name) => [name, { screen: null, loading: true, error: "" }])) as Record<AppName, PanelState>;

function date(value?: string) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function clock(value?: string) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function localInput(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function PanelFeedback({ panel, name, integration }: { panel: PanelState; name: AppName; integration?: Integration }) {
  if (integration?.status === "not_connected") {
    return <p className="unified-feedback">Connect {name === "gmail" || name === "calendar" || name === "drive" ? "Google" : appNames[name]} in Integrations to show your real {appNames[name]} data.</p>;
  }
  if (panel.loading) return <p className="unified-feedback" role="status">Loading {appNames[name]}…</p>;
  if (panel.error) return <p className="unified-feedback error" role="alert">{integration?.status === "needs_attention" ? integration.description : `${appNames[name]} could not be read. Check Integrations and refresh.`}</p>;
  if (panel.screen?.message) return <p className="unified-feedback">{panel.screen.message}</p>;
  if (!panel.screen?.items.length) return <p className="unified-feedback">No recent items available.</p>;
  return null;
}

function ProviderHeading({ name, detail }: { name: AppName; detail?: string }) {
  return <div className="unified-provider-heading">
    <span className={`unified-provider-mark ${name}`}><AppIcon name={name} size={19} /></span>
    <div><h3>{appNames[name]}</h3>{detail && <small>{detail}</small>}</div>
  </div>;
}

export function ConnectedApps({ onOpenPlan }: { onOpenPlan: (plan: LifeEvent) => void }) {
  const [panels, setPanels] = useState<Record<AppName, PanelState>>(initialPanels);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [events, setEvents] = useState<LifeEvent[]>([]);
  const [detail, setDetail] = useState<MailDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [checkingConnections, setCheckingConnections] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [selectedCalendar, setSelectedCalendar] = useState<Item | null>(null);
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [notifyDiscord, setNotifyDiscord] = useState(false);
  const [notifyWhatsapp, setNotifyWhatsapp] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState("");
  const generation = useRef(0);
  const mailGeneration = useRef(0);

  const openMail = useCallback(async (id: string) => {
    const current = ++mailGeneration.current;
    setDetailLoading(true);
    setDetailError("");
    try {
      const next = await api<MailDetail>(`/apps/gmail/${encodeURIComponent(id)}`);
      if (mailGeneration.current === current) setDetail(next);
    } catch (failure) {
      if (mailGeneration.current === current) setDetailError(failure instanceof Error ? failure.message : "Message unavailable.");
    } finally {
      if (mailGeneration.current === current) setDetailLoading(false);
    }
  }, []);

  const load = useCallback(() => {
    const current = ++generation.current;
    mailGeneration.current += 1;
    setDetail(null);
    setDetailError("");
    setPanels(Object.fromEntries(apps.map((name) => [name, {
      screen: null, loading: true, error: "",
    }])) as Record<AppName, PanelState>);
    for (const name of apps) {
      void api<Screen>(`/apps/${name}`).then((screen) => {
        if (generation.current !== current) return;
        setPanels((previous) => ({ ...previous, [name]: { screen, loading: false, error: "" } }));
        if (name === "gmail" && screen.items[0]?.id) void openMail(screen.items[0].id);
      }).catch((failure) => {
        if (generation.current !== current) return;
        setPanels((previous) => ({ ...previous, [name]: {
          screen: null, loading: false,
          error: failure instanceof Error ? failure.message : `${appNames[name]} unavailable.`,
        } }));
      });
    }
    void api<Integration[]>("/integrations").then((value) => {
      if (generation.current === current) setIntegrations(value);
    }).catch(() => { if (generation.current === current) setIntegrations([]); });
    void api<LifeEvent[]>("/events").then((value) => {
      if (generation.current === current) setEvents(value);
    }).catch(() => { if (generation.current === current) setEvents([]); });
  }, [openMail]);

  useEffect(() => { load(); return () => { generation.current += 1; mailGeneration.current += 1; }; }, [load]);

  useEffect(() => {
    let active = true;
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      void api<LifeEvent[]>("/events").then((value) => {
        if (active) setEvents(value);
      }).catch(() => { /* Keep the last known event while temporarily offline. */ });
    }, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  async function checkConnections() {
    setCheckingConnections(true);
    setConnectionError("");
    try {
      setIntegrations(await api<Integration[]>("/integrations/check", "POST", {}));
      load();
    } catch (failure) {
      setConnectionError(failure instanceof Error ? failure.message : "Connection check failed.");
    } finally {
      setCheckingConnections(false);
    }
  }

  function chooseCalendarEvent(event: Item) {
    setSelectedCalendar(event);
    setNewStart(localInput(event.start || ""));
    setNewEnd(localInput(event.end || ""));
    setNotifyDiscord(false);
    setNotifyWhatsapp(false);
    setPlanError("");
  }

  async function planCalendarChange(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCalendar) return;
    setPlanning(true);
    setPlanError("");
    try {
      const start = new Date(newStart);
      const end = new Date(newEnd);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start)
        throw new Error("Choose a valid end time after the start time.");
      if (start.getTime() === new Date(selectedCalendar.start || "").getTime())
        throw new Error("Choose a different start time for this event.");
      const plan = await api<LifeEvent>("/apps/calendar/reschedule-plan", "POST", {
        event_id: selectedCalendar.id,
        expected_etag: selectedCalendar.etag,
        new_start: start.toISOString(),
        new_end: end.toISOString(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        notify_discord: notifyDiscord,
        notify_whatsapp: notifyWhatsapp,
      });
      onOpenPlan(plan);
    } catch (failure) {
      setPlanError(failure instanceof Error ? failure.message : "Calendar plan could not be created.");
    } finally {
      setPlanning(false);
    }
  }

  const discord = panels.discord;
  const gmail = panels.gmail;
  const whatsapp = panels.whatsapp;
  const calendar = panels.calendar;
  const drive = panels.drive;
  const channel = discord.screen?.title || "Configured channel";
  const integrationFor = (name: AppName) => integrations.find((item) => item.id === name);
  const latestEvent = events.find((event) => !event.simulation) || events[0];
  const affected = [...new Set(latestEvent?.actions.map((action) => action.application) || [])];
  const verifiedCount = latestEvent?.actions.filter((action) => action.status === "verified").length || 0;
  const actionCount = latestEvent?.actions.length || 0;
  const progress = actionCount ? Math.round(verifiedCount / actionCount * 100) : 0;

  function focusApplication(name: AppName) {
    const panel = document.querySelector<HTMLElement>(`.unified-${name}`);
    if (!panel) return;
    panel.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    panel.focus({ preventScroll: true });
  }

  return <div className="unified-apps">
    <div className="unified-status-strip">
      <div className="unified-connection-group" aria-label="Integration status">
        <strong>Connections</strong>
        <div className="unified-connection-list">
          {apps.map((name) => {
            const connection = integrationFor(name)?.status;
            const status = connection === "not_connected"
              ? connection
              : panels[name].error
                ? "needs_attention"
                : panels[name].loading
                  ? "checking"
                  : connection || "unknown";
            const live = status === "read_access_verified" || status === "verified" || status === "connected";
            return <span className="unified-connection" key={name} title={`${appNames[name]}: ${status.replaceAll("_", " ")}`}>
              <i className={live ? "live" : "attention"} />{appNames[name]}
            </span>;
          })}
        </div>
        <button type="button" className="unified-check" onClick={() => void checkConnections()} disabled={checkingConnections}>
          {checkingConnections ? "Checking…" : "Check connections"}
        </button>
      </div>
      <div className="unified-ripple" aria-label="Ripple effect" aria-live="polite">
        <Waypoints size={18} />
        <div><strong>Signal flow</strong><span>{latestEvent ? `${latestEvent.title} · ${affected.length} connected ${affected.length === 1 ? "app" : "apps"} · ${verifiedCount}/${actionCount} verified` : "Plan a change to see data move through your connected apps."}</span>
          <div className="unified-ripple-track" role="progressbar" aria-label="Verified actions" aria-valuenow={verifiedCount} aria-valuemin={0} aria-valuemax={actionCount || 1}><i style={{ width: `${progress}%` }} /></div>
        </div>
      </div>
      <button type="button" className="unified-refresh" onClick={load} aria-label="Refresh all connected apps"><RefreshCw size={16} /></button>
    </div>
    {connectionError && <p className="unified-connection-error" role="alert">{connectionError}</p>}

    <div className="unified-main-grid">
      <section className="unified-provider unified-discord" aria-label="Discord screen" tabIndex={-1}>
        <ProviderHeading name="discord" detail={integrationFor("discord")?.status === "not_connected" ? "Connect Discord to view a channel" : "Configured channel · live messages"} />
        <div className="unified-discord-shell">
          <div className="unified-discord-servers" aria-hidden="true"><span>D</span></div>
          <aside className="unified-discord-channels" aria-label="Available Discord channels">
            <strong>CONNECTED SERVER</strong>
            <small>TEXT CHANNELS</small>
            <div className="unified-discord-selected"><Hash size={17} />{channel.replace(/^#/, "")}</div>
            <p>Only the authorized channel is available in LIFEOS.</p>
          </aside>
          <div className="unified-discord-main">
            <div className="unified-discord-channel-title"><Hash size={21} /><strong>{channel.replace(/^#/, "")}</strong><span>Real channel history</span></div>
            <div className="unified-discord-messages" aria-label="Discord channel messages">
              <PanelFeedback panel={discord} name="discord" integration={integrationFor("discord")} />
              {!discord.loading && integrationFor("discord")?.status !== "not_connected" && discord.screen?.items.map((message) => <article className="unified-discord-message" key={message.id}>
                <span className="unified-discord-avatar" aria-hidden="true">
                  {(message.author || "?").slice(0, 1).toUpperCase()}
                  {message.avatar_url && <img src={message.avatar_url} alt="" loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} />}
                </span>
                <div><div className="unified-discord-message-head"><strong>{message.author || "Unknown member"}</strong><time>{date(message.date)}</time></div>
                  <p>{message.content || (message.attachments ? `${message.attachments} attachment(s)` : "Message content unavailable")}</p>
                </div>
              </article>)}
            </div>
            <div className="unified-discord-readonly"><LockKeyhole size={14} />Use LIFEOS approvals to send to {channel}</div>
          </div>
        </div>
      </section>

      <section className="unified-provider unified-gmail" aria-label="Gmail screen" tabIndex={-1}>
        <ProviderHeading name="gmail" detail={integrationFor("gmail")?.status === "not_connected" ? "Connect Google to view inbox" : "Inbox · Google account"} />
        <div className="unified-gmail-shell">
          <aside className="unified-gmail-folders"><span className="selected"><Inbox size={16} />Inbox</span><small>Only your inbox is shown</small></aside>
          <div className="unified-gmail-content">
            <div className="unified-gmail-toolbar"><strong>Inbox</strong><span>{integrationFor("gmail")?.status === "not_connected" ? 0 : gmail.screen?.items.length ?? 0} recent</span></div>
            <div className="unified-gmail-list" aria-label="Inbox messages">
              <PanelFeedback panel={gmail} name="gmail" integration={integrationFor("gmail")} />
              {!gmail.loading && integrationFor("gmail")?.status !== "not_connected" && gmail.screen?.items.map((mail) => <button type="button" key={mail.id}
                className={`unified-gmail-row ${detail?.id === mail.id ? "selected" : ""} ${mail.unread ? "unread" : ""}`}
                onClick={() => void openMail(mail.id)}>
                <span>{mail.from || "Unknown sender"}</span><time>{clock(mail.date)}</time>
                <strong>{mail.subject || "(No subject)"}</strong><small>{mail.preview}</small>
              </button>)}
            </div>
            <div className="unified-gmail-detail" aria-label="Message detail">
              {integrationFor("gmail")?.status === "not_connected" ? <p className="unified-feedback">Connect Google to read Gmail messages.</p> : detailLoading ? <p className="unified-feedback">Opening message…</p> : detailError ? <p className="unified-feedback error" role="alert">{detailError}</p> : detail ? <>
                <h4>{detail.subject || "(No subject)"}</h4><p className="unified-gmail-meta">{detail.from} · {date(detail.date)}</p>
                <div className="unified-gmail-body">{detail.body || "No plain-text body available."}</div>
              </> : <p className="unified-feedback">Select a message to read it here.</p>}
            </div>
          </div>
        </div>
      </section>

      <section className="unified-provider unified-whatsapp" aria-label="WhatsApp screen" tabIndex={-1}>
        <ProviderHeading name="whatsapp" detail={whatsapp.screen?.title || "Configured chat"} />
        <div className="unified-whatsapp-chat" aria-label="WhatsApp conversation">
          <PanelFeedback panel={whatsapp} name="whatsapp" integration={integrationFor("whatsapp")} />
          {!whatsapp.loading && integrationFor("whatsapp")?.status !== "not_connected" && whatsapp.screen?.items.map((message) => <div className={`unified-whatsapp-bubble ${message.outgoing ? "outgoing" : ""}`} key={message.id}>
            <span>{message.content}</span>{message.outgoing && message.status && <small>{message.status}</small>}
          </div>)}
        </div>
        <div className="unified-whatsapp-readonly"><LockKeyhole size={13} />Use LIFEOS approvals to send</div>
      </section>

      <section className="unified-provider unified-calendar" aria-label="Calendar screen" tabIndex={-1}>
        <ProviderHeading name="calendar" detail="Next 14 days" />
        <div className="unified-compact-list" aria-label="Upcoming calendar events">
          <PanelFeedback panel={calendar} name="calendar" integration={integrationFor("calendar")} />
          {!calendar.loading && integrationFor("calendar")?.status !== "not_connected" && calendar.screen?.items.map((event) => <article className="unified-calendar-row" key={event.id}>
            <div className="unified-calendar-date"><strong>{event.start ? new Date(event.start).toLocaleDateString([], { day: "2-digit" }) : "–"}</strong><small>{event.start ? new Date(event.start).toLocaleDateString([], { month: "short" }) : ""}</small></div>
            <div className="unified-calendar-details"><strong>{event.title || "Untitled event"}</strong><small>{date(event.start)}{event.location ? ` · ${event.location}` : ""}</small></div>
            {event.start?.includes("T") && event.end?.includes("T") && event.etag && <button type="button" className="unified-calendar-plan-button" onClick={() => chooseCalendarEvent(event)}>Plan move</button>}
          </article>)}
        </div>
        {selectedCalendar && <form className="unified-calendar-plan" onSubmit={(event) => void planCalendarChange(event)}>
          <strong>Move {selectedCalendar.title || "Calendar event"}</strong>
          <p>Choose the new time. LIFEOS checks availability and prepares a plan for your approval; nothing is changed yet.</p>
          <div className="unified-calendar-plan-fields">
            <label>Start<input type="datetime-local" required value={newStart} onChange={(event) => setNewStart(event.target.value)} /></label>
            <label>End<input type="datetime-local" required value={newEnd} onChange={(event) => setNewEnd(event.target.value)} /></label>
          </div>
          <label className="unified-calendar-plan-check"><input type="checkbox" checked={notifyDiscord} onChange={(event) => setNotifyDiscord(event.target.checked)} disabled={integrationFor("discord")?.status === "not_connected"} />Notify the configured Discord channel after Calendar verification</label>
          <label className="unified-calendar-plan-check"><input type="checkbox" checked={notifyWhatsapp} onChange={(event) => setNotifyWhatsapp(event.target.checked)} disabled={integrationFor("whatsapp")?.status === "not_connected"} />Notify the configured WhatsApp contact after Calendar verification</label>
          {planError && <p className="unified-calendar-plan-error" role="alert">{planError}</p>}
          <div className="unified-calendar-plan-actions"><button type="button" onClick={() => setSelectedCalendar(null)}>Cancel</button><button type="submit" disabled={planning}>{planning ? "Checking Calendar…" : "Review plan"}</button></div>
        </form>}
      </section>

      <section className="unified-provider unified-drive" aria-label="Drive screen" tabIndex={-1}>
        <ProviderHeading name="drive" detail="Recent files" />
        <div className="unified-drive-columns"><span>Name</span><span>Modified</span></div>
        <div className="unified-compact-list" aria-label="Recent Drive files">
          <PanelFeedback panel={drive} name="drive" integration={integrationFor("drive")} />
          {!drive.loading && integrationFor("drive")?.status !== "not_connected" && drive.screen?.items.map((file) => <article className="unified-drive-row" key={file.id}>
            <AppIcon name="drive" size={16} /><span title={file.name}>{file.name || "Untitled file"}</span><time>{file.modified ? new Date(file.modified).toLocaleDateString() : ""}</time>
          </article>)}
        </div>
      </section>

    </div>
    <section className="unified-impact-panel" aria-label="Signal flow details">
      <div className="unified-impact-intro"><Waypoints size={18} /><div><h3>Signal flow</h3><p>{latestEvent ? latestEvent.title : "Plan a change to see which connected apps receive the signal."}</p></div></div>
      {latestEvent && <div className="unified-impact-actions">
        {latestEvent.actions.length ? latestEvent.actions.map((action) => <button type="button" className={`unified-impact-action ${["executing", "verifying", "running"].includes(action.status) ? "is-busy" : ""}`} key={`${action.id}-${action.status}`} onClick={() => focusApplication(action.application)} aria-label={`View ${appNames[action.application] || action.application} for ${action.title}`}>
          <span className="unified-impact-icon"><AppIcon name={action.application} size={16} /></span>
          <div><strong>{appNames[action.application] || action.application}</strong><small>{action.title}</small></div>
          <Status value={action.status} />
        </button>) : <p>No connected actions were proposed for this event.</p>}
      </div>}
    </section>
  </div>;
}
