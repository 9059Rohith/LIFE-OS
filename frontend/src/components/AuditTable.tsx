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
      <details className="metrics">
        <summary>
          <Database size={16} />
          Measured workspace metrics
        </summary>
        <pre>{display(metrics)}</pre>
      </details>
    </>
  );
}
