import { ArrowUpRight, ShieldCheck } from "lucide-react";
import type { Integration } from "../types";
import { AppIcon, Status } from "./Common";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { SourceMonitoring } from "./SourceMonitoring";

export function IntegrationList({
  integrations,
  mode,
  connect,
}: {
  integrations: Integration[];
  mode: string;
  connect: () => Promise<void>;
}) {
  const [checks, setChecks] = useState<Integration[] | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  const initialCheck = useRef(false);
  const checkConnections = useCallback(async () => {
    setChecking(true);
    setCheckError("");
    try {
      setChecks(await api<Integration[]>("/integrations/check", "POST", {}));
    } catch (error) {
      setCheckError(
        error instanceof Error ? error.message : "Unable to check connections.",
      );
    } finally {
      setChecking(false);
    }
  }, []);
  useEffect(() => {
    if (mode !== "demo" && integrations.some((item) => item.status === "configured_unverified") && !initialCheck.current) {
      initialCheck.current = true;
      void checkConnections();
    }
  }, [mode, integrations, checkConnections]);
  return (
    <>
      <div className="notice">
        <ShieldCheck size={20} />
        <span>
          {mode === "demo"
            ? "Demo connections use isolated local data. Live credentials are never used in demo mode."
            : "Live integrations require valid credentials. Configuration does not imply a verified connection."}
        </span>
      </div>
      {mode !== "demo" && (
        <div className="notice">
          <button
            className="button small"
            disabled={checking}
            onClick={() => void checkConnections()}
          >
            {checking ? "Checking access…" : "Check API access"}
          </button>
          <span aria-live="polite">
            {checking
              ? "Checking connected services. The WhatsApp browser may take up to 90 seconds."
              : checks
                ? "Results from your last check. Read access does not verify message delivery."
                : "Check permissions without sending messages or changing calendar events."}
          </span>
        </div>
      )}
      {checkError && <p role="alert">{checkError}</p>}
      <div className="integration-list">
        {(checks ?? integrations).map((item) => (
          <div className="integration-row" key={item.id}>
            <span className={`app-mark ${item.id}`}>
              <AppIcon name={item.id} size={25} />
            </span>
            <div>
              <h3>{item.name}</h3>
              <p>{item.description}</p>
            </div>
            <Status value={item.status} />
            {["gmail", "calendar", "drive"].includes(item.id) &&
              mode !== "demo" &&
              item.status === "not_connected" && (
                <button className="button small" onClick={() => void connect()}>
                  Connect Google
                  <ArrowUpRight size={14} />
                </button>
              )}
          </div>
        ))}
      </div>
      <SourceMonitoring />
    </>
  );
}
