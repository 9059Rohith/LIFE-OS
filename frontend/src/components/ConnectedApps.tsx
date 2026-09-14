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
const apps: AppName[] = ["discord", "gmail", "whatsapp", "calendar", "drive", "maps"];
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

function PanelFeedback({ panel, name }: { panel: PanelState; name: AppName }) {
  if (panel.loading) return <p className="unified-feedback" role="status">Loading {appNames[name]}…</p>;
  if (panel.error) return <p className="unified-feedback error" role="alert">{panel.error}</p>;
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

export function ConnectedApps() {
  const [panels, setPanels] = useState<Record<AppName, PanelState>>(initialPanels);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [events, setEvents] = useState<LifeEvent[]>([]);
  const [detail, setDetail] = useState<MailDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [checkingConnections, setCheckingConnections] = useState(false);
  const [connectionError, setConnectionError] = useState("");
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
    setPanels((previous) => Object.fromEntries(apps.map((name) => [name, {
      ...previous[name], loading: true, error: "",
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

  async function checkConnections() {
    setCheckingConnections(true);
    setConnectionError("");
    try {
      setIntegrations(await api<Integration[]>("/integrations/check", "POST", {}));
    } catch (failure) {
      setConnectionError(failure instanceof Error ? failure.message : "Connection check failed.");
    } finally {
      setCheckingConnections(false);
    }
  }

  const discord = panels.discord;
  const gmail = panels.gmail;
  const whatsapp = panels.whatsapp;
  const calendar = panels.calendar;
  const drive = panels.drive;
  const maps = panels.maps;
  const channel = discord.screen?.title || "Configured channel";
  const latestEvent = events.find((event) => !event.simulation) || events[0];
  const affected = [...new Set(latestEvent?.actions.map((action) => action.application) || [])];

  return <div className="unified-apps">
    <div className="unified-status-strip">
      <div className="unified-connection-group" aria-label="Integration status">
        <strong>Connections</strong>
        <div className="unified-connection-list">
          {apps.map((name) => {
            const status = integrations.find((item) => item.id === name)?.status || "unknown";
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
      <div className="unified-ripple" aria-label="Ripple effect">
        <Waypoints size={18} />
        <div><strong>Ripple effect</strong><span>{latestEvent ? `${latestEvent.title} · ${affected.length} connected ${affected.length === 1 ? "app" : "apps"}` : "Plan a change to see its connected impact."}</span></div>
      </div>
      <button type="button" className="unified-refresh" onClick={load} aria-label="Refresh all connected apps"><RefreshCw size={16} /></button>
    </div>
    {connectionError && <p className="unified-connection-error" role="alert">{connectionError}</p>}

    <div className="unified-main-grid">
      <section className="unified-provider unified-discord" aria-label="Discord screen">
        <ProviderHeading name="discord" detail="Configured channel · live messages" />
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
              <PanelFeedback panel={discord} name="discord" />
              {!discord.loading && discord.screen?.items.map((message) => <article className="unified-discord-message" key={message.id}>
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

      <section className="unified-provider unified-gmail" aria-label="Gmail screen">
        <ProviderHeading name="gmail" detail="Inbox · connected Google account" />
        <div className="unified-gmail-shell">
          <aside className="unified-gmail-folders"><span className="selected"><Inbox size={16} />Inbox</span><small>Only your inbox is shown</small></aside>
          <div className="unified-gmail-content">
            <div className="unified-gmail-toolbar"><strong>Inbox</strong><span>{gmail.screen?.items.length ?? 0} recent</span></div>
            <div className="unified-gmail-list" aria-label="Inbox messages">
              <PanelFeedback panel={gmail} name="gmail" />
              {!gmail.loading && gmail.screen?.items.map((mail) => <button type="button" key={mail.id}
                className={`unified-gmail-row ${detail?.id === mail.id ? "selected" : ""} ${mail.unread ? "unread" : ""}`}
                onClick={() => void openMail(mail.id)}>
                <span>{mail.from || "Unknown sender"}</span><time>{clock(mail.date)}</time>
                <strong>{mail.subject || "(No subject)"}</strong><small>{mail.preview}</small>
              </button>)}
            </div>
            <div className="unified-gmail-detail" aria-label="Message detail">
              {detailLoading ? <p className="unified-feedback">Opening message…</p> : detailError ? <p className="unified-feedback error" role="alert">{detailError}</p> : detail ? <>
                <h4>{detail.subject || "(No subject)"}</h4><p className="unified-gmail-meta">{detail.from} · {date(detail.date)}</p>
                <div className="unified-gmail-body">{detail.body || "No plain-text body available."}</div>
              </> : <p className="unified-feedback">Select a message to read it here.</p>}
            </div>
          </div>
        </div>
      </section>

      <section className="unified-provider unified-whatsapp" aria-label="WhatsApp screen">
        <ProviderHeading name="whatsapp" detail={whatsapp.screen?.title || "Configured chat"} />
        <div className="unified-whatsapp-chat" aria-label="WhatsApp conversation">
          <PanelFeedback panel={whatsapp} name="whatsapp" />
          {!whatsapp.loading && whatsapp.screen?.items.map((message) => <div className={`unified-whatsapp-bubble ${message.outgoing ? "outgoing" : ""}`} key={message.id}>
            <span>{message.content}</span>{message.outgoing && message.status && <small>{message.status}</small>}
          </div>)}
        </div>
        <div className="unified-whatsapp-readonly"><LockKeyhole size={13} />Use LIFEOS approvals to send</div>
      </section>

      <section className="unified-provider unified-calendar" aria-label="Calendar screen">
        <ProviderHeading name="calendar" detail="Next 14 days" />
        <div className="unified-compact-list" aria-label="Upcoming calendar events">
          <PanelFeedback panel={calendar} name="calendar" />
          {!calendar.loading && calendar.screen?.items.map((event) => <article className="unified-calendar-row" key={event.id}>
            <div className="unified-calendar-date"><strong>{event.start ? new Date(event.start).toLocaleDateString([], { day: "2-digit" }) : "–"}</strong><small>{event.start ? new Date(event.start).toLocaleDateString([], { month: "short" }) : ""}</small></div>
            <div><strong>{event.title || "Untitled event"}</strong><small>{date(event.start)}{event.location ? ` · ${event.location}` : ""}</small></div>
          </article>)}
        </div>
      </section>

      <section className="unified-provider unified-drive" aria-label="Drive screen">
        <ProviderHeading name="drive" detail="Recent files" />
        <div className="unified-drive-columns"><span>Name</span><span>Modified</span></div>
        <div className="unified-compact-list" aria-label="Recent Drive files">
          <PanelFeedback panel={drive} name="drive" />
          {!drive.loading && drive.screen?.items.map((file) => <article className="unified-drive-row" key={file.id}>
            <AppIcon name="drive" size={16} /><span title={file.name}>{file.name || "Untitled file"}</span><time>{file.modified ? new Date(file.modified).toLocaleDateString() : ""}</time>
          </article>)}
        </div>
      </section>

      <section className="unified-provider unified-maps" aria-label="Maps screen">
        <ProviderHeading name="maps" detail="Routes and travel" />
        <div className="unified-maps-content"><PanelFeedback panel={maps} name="maps" /></div>
      </section>
    </div>
    <section className="unified-impact-panel" aria-label="Ripple effect details">
      <div className="unified-impact-intro"><Waypoints size={18} /><div><h3>Ripple effect</h3><p>{latestEvent ? latestEvent.title : "Plan a change to see which connected apps it affects."}</p></div></div>
      {latestEvent && <div className="unified-impact-actions">
        {latestEvent.actions.length ? latestEvent.actions.map((action) => <article className="unified-impact-action" key={action.id}>
          <span className="unified-impact-icon"><AppIcon name={action.application} size={16} /></span>
          <div><strong>{appNames[action.application]}</strong><small>{action.title}</small></div>
          <Status value={action.status} />
        </article>) : <p>No connected actions were proposed for this event.</p>}
      </div>}
    </section>
  </div>;
}
