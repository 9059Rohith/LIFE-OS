import { Search, Download, Database } from "lucide-react";
import { display } from "./Common";

export function AuditTable({
  audit,
  metrics,
  query,
  setQuery,
  download,
}: {
  audit: Record<string, unknown>[];
  metrics: Record<string, unknown>;
  query: string;
  setQuery: (value: string) => void;
  download: () => void;
}) {
  return (
    <>
      <div className="audit-tools">
        <label className="search-field">
          <Search size={16} />
          <input
            aria-label="Search audit trail"
            placeholder="Search records…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button className="button small" onClick={download}>
          <Download size={15} />
          Export JSON
        </button>
      </div>
      <div className="panel audit-table">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Application</th>
              <th>Record</th>
            </tr>
          </thead>
          <tbody>
            {audit
              .filter((row) =>
                JSON.stringify(row).toLowerCase().includes(query.toLowerCase()),
              )
              .map((row, i) => (
                <tr key={i}>
                  <td>
                    {row.timestamp || row.created_at
                      ? new Date(
                          typeof row.timestamp === "number"
                            ? row.timestamp * 1000
                            : String(row.timestamp || row.created_at),
                        ).toLocaleString()
                      : String(i + 1)}
                  </td>
                  <td>
                    {String(
                      row.action || row.stage || row.kind || "Audit entry",
                    )}
                  </td>
                  <td>{String(row.application || "LIFEOS")}</td>
                  <td>
                    <details>
                      <summary>Inspect evidence</summary>
                      <pre>{display(row)}</pre>
                    </details>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        {!audit.length && (
          <p className="loading-block">
            Your audit trail starts with your first event.
          </p>
        )}
      </div>
      <div className="panel metrics-panel" style={{ marginTop: "2rem" }}>
        <div className="panel-heading">
          <h2>
            <Database size={17} style={{ marginRight: "0.5rem", verticalAlign: "middle" }} />
            Usage & Cost Metrics
          </h2>
          <span className="count">{metrics.samples ? String(metrics.samples) : 0} samples</span>
        </div>
        <div className="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
          <div className="metric-card" style={{ padding: "1rem", background: "var(--bg-layer-2)", borderRadius: "8px" }}>
            <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--text-secondary)", fontSize: "0.85rem" }}>Events / Actions</h4>
            <div style={{ fontSize: "1.5rem", fontWeight: "600" }}>{String(metrics.events || 0)} / {String(metrics.tool_calls || 0)}</div>
          </div>
          <div className="metric-card" style={{ padding: "1rem", background: "var(--bg-layer-2)", borderRadius: "8px" }}>
            <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--text-secondary)", fontSize: "0.85rem" }}>Total Tokens</h4>
            <div style={{ fontSize: "1.5rem", fontWeight: "600" }}>
              {(metrics.model_token_usage as any)?.total_tokens?.toLocaleString() || 0}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
              In: {(metrics.model_token_usage as any)?.input_tokens?.toLocaleString() || 0} | 
              Out: {(metrics.model_token_usage as any)?.output_tokens?.toLocaleString() || 0}
            </div>
          </div>
          <div className="metric-card" style={{ padding: "1rem", background: "var(--bg-layer-2)", borderRadius: "8px" }}>
            <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--text-secondary)", fontSize: "0.85rem" }}>Estimated Cost</h4>
            <div style={{ fontSize: "1.5rem", fontWeight: "600", color: "var(--color-primary)" }}>
              ${(((metrics.model_token_usage as any)?.input_tokens || 0) * (0.150 / 1000000) + ((metrics.model_token_usage as any)?.output_tokens || 0) * (0.600 / 1000000)).toFixed(4)}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>Based on gpt-4o-mini pricing</div>
          </div>
          <div className="metric-card" style={{ padding: "1rem", background: "var(--bg-layer-2)", borderRadius: "8px" }}>
            <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--text-secondary)", fontSize: "0.85rem" }}>Latency (p95)</h4>
            <div style={{ fontSize: "1.5rem", fontWeight: "600" }}>
              {(metrics.latency_ms as any)?.p95 ? `${(metrics.latency_ms as any).p95}ms` : 'N/A'}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
