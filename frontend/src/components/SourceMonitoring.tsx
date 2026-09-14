import { useEffect, useState } from "react";
import { api } from "../api";

interface Monitoring {
  enabled: boolean;
  sources: ("gmail" | "discord")[];
  interval_seconds: number;
  last_checked: number | null;
  results: { status: string; event_id?: string }[];
  error: string | null;
  running: boolean;
}

export function SourceMonitoring() {
  const [state, setState] = useState<Monitoring | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void api<Monitoring>("/ingestion")
      .then((value) => {
        if (active) setState(value);
      })
      .catch(() => {
        if (active) setError("Unable to load source monitoring.");
      });
    return () => {
      active = false;
    };
  }, []);
  async function run(scan = false) {
    if (!state) return;
    setBusy(true);
    setError("");
    try {
      setState(
        await api<Monitoring>(
          scan ? "/ingestion/scan" : "/ingestion",
          "POST",
          scan
            ? {}
            : {
                enabled: state.enabled,
                sources: state.sources,
                interval_seconds: state.interval_seconds,
              },
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Monitoring request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel settings-form" aria-label="Source monitoring">
      <h3>Watch for scheduling changes</h3>
      <p>
        Check recent Gmail and Discord messages and prepare up to three plans
        per scan. Every external action still needs approval. Live messages must
        contain an explicit date such as 2026-09-15.
      </p>
      {state && (
        <>
          <label>
            <input
              type="checkbox"
              checked={state.enabled}
              disabled={busy}
              onChange={(e) =>
                setState({ ...state, enabled: e.target.checked })
              }
            />{" "}
            Enable monitoring
          </label>
          {(["gmail", "discord"] as const).map((source) => (
            <label key={source}>
              <input
                type="checkbox"
                checked={state.sources.includes(source)}
                disabled={busy}
                onChange={(e) =>
                  setState({
                    ...state,
                    sources: e.target.checked
                      ? [...state.sources, source]
                      : state.sources.filter((s) => s !== source),
                  })
                }
              />{" "}
              {source === "gmail" ? "Gmail" : "Discord"}
            </label>
          ))}
          <label htmlFor="scan-interval">Check every (seconds)</label>
          <input
            id="scan-interval"
            type="number"
            min={60}
            max={86400}
            value={state.interval_seconds}
            disabled={busy}
            onChange={(e) =>
              setState({ ...state, interval_seconds: Number(e.target.value) })
            }
          />
          <button
            className="button primary"
            disabled={
              busy ||
              !state.sources.length ||
              state.interval_seconds < 60 ||
              state.interval_seconds > 86400
            }
            onClick={() => void run()}
          >
            Save monitoring
          </button>
          <button
            className="button"
            disabled={busy || !state.enabled}
            onClick={() => void run(true)}
          >
            {busy ? "Checking sources…" : "Scan now"}
          </button>
          <p aria-live="polite">
            {state.last_checked
              ? `Last checked: ${new Date(state.last_checked * 1000).toLocaleString()}. ${state.results.filter((r) => r.status === "planned").length} plans prepared; view them in Overview.`
              : "No sources checked yet."}
          </p>
          {state.error && <p role="alert">{state.error}</p>}
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
