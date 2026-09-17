import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../api";
import type { Integration, AppRecords, Page } from "../types";
import { IntegrationList } from "./IntegrationList";
import { ApplicationRecords } from "./ApplicationRecords";
import { ConnectedApps } from "./ConnectedApps";
import { PrivacyControls } from "./PrivacyControls";
import { AuditTable } from "./AuditTable";
import {
  WorkspaceSettings,
  type WorkspacePreferences,
} from "./WorkspaceSettings";
export function WorkspacePages({
  page,
  onError,
  mode,
}: {
  page: Page;
  onError: (message: string) => void;
  mode: string;
}) {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [apps, setApps] = useState<AppRecords[]>([]);
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [settings, setSettings] = useState<WorkspacePreferences>({
    name: "",
    timezone: "Asia/Kolkata",
    retention_days: 30,
  });
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState(false);
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const loadGeneration = useRef(0);
  const errorHandler = useRef(onError);
  useEffect(() => {
    errorHandler.current = onError;
  }, [onError]);
  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    const current = () => generation === loadGeneration.current;
    setLoading(true);
    try {
      if (page === "integrations") {
        const result = await api<Integration[]>("/integrations");
        if (current()) setIntegrations(result);
      }
      if (page === "applications" && mode === "demo") {
        const result = await api<AppRecords[]>("/demo/apps");
        if (current()) setApps(result);
      }
      if (page === "audit") {
        const [records, measured] = await Promise.all([
          api<Record<string, unknown>[]>("/audit"),
          api<Record<string, unknown>>("/metrics"),
        ]);
        if (current()) {
          setAudit(records);
          setMetrics(measured);
        }
      }
      if (page === "settings") {
        const result = await api<WorkspacePreferences>("/settings");
        if (current()) {
          setSettings(result);
          setSaved(false);
        }
      }
    } catch (error) {
      if (current())
        errorHandler.current(
          error instanceof Error ? error.message : "Unable to load workspace.",
        );
    } finally {
      if (current()) setLoading(false);
    }
  }, [page, mode]);
  useEffect(() => {
    void load();
    return () => {
      loadGeneration.current += 1;
    };
  }, [load]);
  useEffect(() => {
    if (page !== "integrations") return;
    const refresh = () => { if (!document.hidden) void load(); };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [load, page]);
  async function connect() {
    try {
      const result = await api<{ url: string }>("/integrations/google/connect");
      const target = new URL(result.url);
      if (
        target.protocol !== "https:" ||
        target.hostname !== "accounts.google.com"
      )
        throw new Error("The server returned an invalid OAuth URL.");
      window.location.assign(target.href);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Connection failed.");
    }
  }
  async function save() {
    try {
      await api("/settings", "PATCH", settings);
      setSaved(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Unable to save settings.");
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "lifeos-audit.json";
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="workspace-page">
      <div className="workspace-title">
        <div>
          <h2>
            {page === "integrations"
              ? "Your connected world."
              : page === "applications"
                ? mode === "demo" ? "Inside the demo applications." : "Your connected apps."
                : page === "audit"
                  ? "A record of every decision."
                  : "Make LIFEOS yours."}
          </h2>
          <p>
            {page === "integrations"
              ? "Explicit access. Clear boundaries. One place to manage it all."
              : page === "applications"
                ? mode === "demo" ? "Persisted local application state. These are simulated services, not your personal accounts." : "Live account summaries appear here. The Windows app opens the actual Discord and WhatsApp websites."
                : page === "audit"
                  ? "Trace approvals, execution, and independent verification."
                  : "Preferences for this workspace."}
          </p>
        </div>
        <button className="button small" onClick={() => void load()}>
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="loading-block">Loading workspace…</div>
      ) : (
        <>
          {page === "integrations" && (
            <IntegrationList
              integrations={integrations}
              mode={mode}
              connect={connect}
            />
          )}
          {page === "applications" && (mode === "demo" ? <ApplicationRecords apps={apps} /> : <ConnectedApps />)}
          {page === "audit" && (
            <AuditTable
              audit={audit}
              metrics={metrics}
              query={query}
              setQuery={setQuery}
              download={download}
            />
          )}
          {page === "settings" && (
            <>
              <WorkspaceSettings
                settings={settings}
                setSettings={setSettings}
                saved={saved}
                setSaved={setSaved}
                save={save}
              />
              <PrivacyControls />
            </>
          )}
        </>
      )}
    </div>
  );
}
