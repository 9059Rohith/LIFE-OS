import { useEffect, useRef, useState } from "react";
import { X, ShieldCheck, Undo2, LockKeyhole, Check } from "lucide-react";
import type { Action } from "../types";
import { AppIcon, Status, display, appNames } from "./Common";
export function ActionDialog({
  action,
  busy,
  onClose,
  onSave,
  onReject,
  onApprove,
  readOnly = false,
}: {
  action: Action;
  busy: boolean;
  onClose: () => void;
  onSave: (args: Record<string, unknown>) => Promise<void>;
  onReject: () => Promise<void>;
  onApprove: () => Promise<void>;
  readOnly?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(JSON.stringify(action.arguments, null, 2));
  const [error, setError] = useState("");
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  const editable =
    !readOnly &&
    ["pending", "proposed", "awaiting_approval", "approved", "failed"].includes(
      action.status,
    );
  async function save() {
    try {
      const parsed: unknown = JSON.parse(draft);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
        throw new Error("Arguments must be a JSON object.");
      await onSave(parsed as Record<string, unknown>);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save.");
    }
  }
  return (
    <dialog
      ref={dialog}
      className="action-dialog"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === dialog.current) onClose();
      }}
    >
      <div className="dialog-heading">
        <div className={`app-mark ${action.application}`}>
          <AppIcon name={action.application} size={23} />
        </div>
        <div>
          <small>
            {appNames[action.application]} · {action.risk.toLowerCase()} risk
          </small>
          <h2>{action.title}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Close review"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div className="dialog-content">
        <Status value={action.status} />
        <p>{action.reason}</p>
        <div className="detail-grid">
          <div>
            <small>RECIPIENT / TARGET</small>
            <strong>{action.target || "Read-only context"}</strong>
          </div>
          <div>
            <small>REVERSIBILITY</small>
            <strong>
              {action.reversible ? (
                <>
                  <Undo2 size={14} />
                  Can be compensated
                </>
              ) : (
                <>
                  <LockKeyhole size={14} />
                  Cannot be recalled
                </>
              )}
            </strong>
          </div>
        </div>
        <div className="preview-heading">
          <h3>Exact action content</h3>
          {editable && (
            <button
              className="text-button"
              onClick={() => setEditing(!editing)}
            >
              {editing ? "Cancel editing" : "Edit action"}
            </button>
          )}
        </div>
        {editing ? (
          <>
            <label htmlFor="arguments">Action arguments (JSON)</label>
            <textarea
              id="arguments"
              className="code-editor"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <p className="field-note">
              Saving invalidates approvals for the current plan. Review and
              approve again.
            </p>
            <button
              className="button primary small"
              disabled={busy}
              onClick={() => void save()}
            >
              Save changes
            </button>
          </>
        ) : (
          <dl className="argument-list">
            {Object.entries(action.arguments).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd>{display(value)}</dd>
              </div>
            ))}
          </dl>
        )}
        {action.evidence && (
          <div className="evidence-box">
            <h3>
              <ShieldCheck size={16} />
              Verification evidence
            </h3>
            <pre>{display(action.evidence)}</pre>
          </div>
        )}
        {action.error && (
          <p role="alert" className="inline-error">
            {action.error}
          </p>
        )}
        {action.compensation_status && (
          <div className="evidence-box">
            <h3>Undo: {action.compensation_status.replaceAll("_", " ")}</h3>
            {action.compensation_evidence && (
              <pre>{display(action.compensation_evidence)}</pre>
            )}
            {action.compensation_error && (
              <p role="alert">{action.compensation_error}</p>
            )}
          </div>
        )}
        {error && (
          <p role="alert" className="inline-error">
            {error}
          </p>
        )}
        <p className="hash-label">
          Approval bound to action · {action.arguments_hash?.slice(0, 16)}
        </p>
      </div>
      <footer>
        {editable && (
          <button
            className="button danger"
            disabled={busy}
            onClick={() => void onReject()}
          >
            Reject action
          </button>
        )}
        <button className="button" onClick={onClose}>
          Close
        </button>
        {editable && action.requires_approval && (
          <button
            className="button primary"
            disabled={busy}
            onClick={() => void onApprove()}
          >
            <Check size={16} />
            Approve this action
          </button>
        )}
      </footer>
    </dialog>
  );
}
