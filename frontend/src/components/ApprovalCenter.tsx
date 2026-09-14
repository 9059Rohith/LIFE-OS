import {
  ShieldCheck,
  Play,
  Check,
  ArrowUpRight,
  FlaskConical,
  RotateCcw,
  Square,
} from "lucide-react";
import type { Action, LifeEvent } from "../types";
import { AppIcon, Status } from "./Common";
export function ApprovalCenter({
  event,
  busy,
  onAction,
  onReview,
}: {
  event: LifeEvent | null;
  busy: boolean;
  onAction: (operation: string, ids?: string[]) => void;
  onReview: (action: Action) => void;
}) {
  if (event && ["blocked", "clarification_required"].includes(event.status))
    return null;
  if (!event)
    return (
      <section className="panel approval-empty">
        <ShieldCheck size={25} />
        <div>
          <h2>Your approval comes first.</h2>
          <p>
            Exact recipients, exact changes, and clear risks. You decide what
            goes ahead.
          </p>
        </div>
      </section>
    );
  const terminal = ["cancelled", "compensated", "resolved"].includes(
    event.status,
  );
  const uncertain = event.actions.some((a) => a.status === "uncertain");
  const pending = event.actions.filter(
    (a) =>
      a.requires_approval &&
      !terminal &&
      ["pending", "awaiting_approval", "proposed", "failed"].includes(a.status),
  );
  const ready =
    !terminal &&
    !uncertain &&
    (event.actions.some(
      (a) => a.requires_approval && a.status === "approved",
    ) ||
      event.actions.every((a) => !a.requires_approval));
  const running = ["executing", "verifying", "running"].includes(event.status);
  return (
    <section className="panel approval-panel" aria-label="Approval center">
      <div className="panel-heading">
        <div>
          <h2>
            {terminal && event.status !== "resolved"
              ? "This plan is closed."
              : event.simulation
                ? "Explore the possibilities."
                : event.status === "resolved"
                  ? "Every action accounted for."
                  : "Your approval comes first."}
          </h2>
          <p>
            {terminal
              ? event.summary
              : event.simulation
                ? "Simulation only. No application changes can execute."
                : "Review exactly what LIFEOS will do before anything is sent or changed."}
          </p>
        </div>
        <div className="approval-controls">
          {event.simulation && !terminal ? (
            <button
              className="button primary small"
              disabled={busy}
              onClick={() => onAction("apply")}
            >
              <FlaskConical size={14} />
              Apply plan
            </button>
          ) : (
            <>
              {pending.length > 0 && (
                <button
                  className="button small"
                  disabled={busy}
                  onClick={() =>
                    onAction(
                      "approve",
                      pending.map((a) => a.id),
                    )
                  }
                >
                  <Check size={14} />
                  Approve all ({pending.length})
                </button>
              )}
              {ready && !running && (
                <button
                  className="button primary small"
                  disabled={busy}
                  onClick={() => onAction("execute")}
                >
                  <Play size={13} />
                  Execute approved
                </button>
              )}
              {running && (
                <button
                  className="button small danger"
                  onClick={() => onAction("cancel")}
                >
                  <Square size={13} />
                  Cancel
                </button>
              )}
            </>
          )}
        </div>
      </div>
      <div className="approval-rows">
        {event.actions.map((a) => (
          <div className="approval-row" key={a.id}>
            <span className={`app-mark ${a.application}`}>
              <AppIcon name={a.application} />
            </span>
            <div className="action-name">
              <strong>{a.title}</strong>
              <small>{a.target || a.reason}</small>
            </div>
            <span className="risk-label">{a.risk.toLowerCase()} risk</span>
            <Status value={a.status} />
            <button className="review-button" onClick={() => onReview(a)}>
              Review
              <ArrowUpRight size={13} />
            </button>
            {a.requires_approval &&
            ["pending", "awaiting_approval", "proposed", "failed"].includes(
              a.status,
            ) &&
            !event.simulation &&
            !terminal ? (
              <button
                className="button primary small"
                disabled={busy}
                onClick={() => onAction("approve", [a.id])}
              >
                Approve
              </button>
            ) : (
              <span className="row-spacer" />
            )}
          </div>
        ))}
      </div>
      {[
        "partial",
        "partial_failure",
        "failed",
        "needs_attention",
        "needs_human",
      ].includes(event.status) && (
        <div className="resolution-note">
          <span>
            {uncertain
              ? "Delivery is uncertain. Inspect the provider before taking any further action; automatic retry is disabled."
              : "Some actions need attention. Review the evidence before retrying."}
          </span>
          {!uncertain && (
            <button
              className="button small"
              disabled={busy}
              onClick={() => onAction("retry")}
            >
              <RotateCcw size={14} />
              Retry eligible actions
            </button>
          )}
        </div>
      )}
      {event.status === "resolved" && (
        <div className="resolution-note success">
          <span>
            <ShieldCheck size={16} />
            Resolved with read-back verification.
          </span>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => onAction("undo")}
          >
            Undo reversible changes
          </button>
        </div>
      )}
    </section>
  );
}
