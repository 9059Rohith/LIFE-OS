import type { AppRecords } from "../types";
import { AppIcon, appNames, display } from "./Common";

export function ApplicationRecords({ apps }: { apps: AppRecords[] }) {
  return (
    <div className="app-records">
      {apps.map((app) => (
        <section className="panel" key={app.application}>
          <div className="panel-heading">
            <h3>
              <AppIcon name={app.application} />
              {appNames[app.application]}
            </h3>
            <span className="small-muted">{app.records.length} records</span>
          </div>
          {app.records.length ? (
            app.records.map((record, i) => (
              <details key={i} className="record">
                <summary>
                  {display(
                    record.title ||
                      record.subject ||
                      record.name ||
                      record.content ||
                      record.id ||
                      "Application record",
                  ).slice(0, 120)}
                </summary>
                <pre>{display(record)}</pre>
              </details>
            ))
          ) : (
            <p className="record empty-record">
              No records. Run a demo to populate this application.
            </p>
          )}
        </section>
      ))}
    </div>
  );
}
