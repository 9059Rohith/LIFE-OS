import { useState } from "react";
import { api } from "../api";

export function PrivacyControls() {
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function perform(kind: "export" | "disconnect" | "delete") {
    setBusy(true);
    setMessage("");
    try {
      if (kind === "export") {
        const data = await api("/privacy/export");
        const url = URL.createObjectURL(
          new Blob([JSON.stringify(data, null, 2)], {
            type: "application/json",
          }),
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = "lifeos-workspace.json";
        link.click();
        URL.revokeObjectURL(url);
        setMessage("Workspace export downloaded. Credentials are excluded.");
      } else if (kind === "disconnect") {
        await api("/privacy/disconnect/google", "POST", {});
        setMessage(
          "Google disconnected in LIFEOS and monitoring paused. Manage separate provider permissions in your Google account.",
        );
      } else {
        await api("/privacy/delete", "POST", { confirmation });
        window.location.reload();
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Privacy request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel settings-form" aria-label="Data controls">
      <h3>Your data and connections</h3>
      <p>
        Export your local records or disconnect Google. Deleting workspace data
        removes local history, saved Google access and sessions; it does not
        delete external messages, environment credentials or the linked WhatsApp
        browser profile.
      </p>
      <button
        className="button"
        disabled={busy}
        onClick={() => void perform("export")}
      >
        Export workspace
      </button>
      <button
        className="button"
        disabled={busy}
        onClick={() => void perform("disconnect")}
      >
        Disconnect Google
      </button>
      <label htmlFor="delete-confirmation">
        Type DELETE MY DATA to erase this workspace
      </label>
      <input
        id="delete-confirmation"
        value={confirmation}
        onChange={(e) => setConfirmation(e.target.value)}
        autoComplete="off"
      />
      <button
        className="button danger"
        disabled={busy || confirmation !== "DELETE MY DATA"}
        onClick={() => void perform("delete")}
      >
        Delete workspace data
      </button>
      {message && <p role="status">{message}</p>}
    </section>
  );
}
