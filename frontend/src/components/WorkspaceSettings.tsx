import { Check, Settings2 } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
export interface WorkspacePreferences {
  name: string;
  timezone: string;
  retention_days: number;
}

export function WorkspaceSettings({
  settings,
  setSettings,
  saved,
  setSaved,
  save,
}: {
  settings: WorkspacePreferences;
  setSettings: Dispatch<SetStateAction<WorkspacePreferences>>;
  saved: boolean;
  setSaved: (value: boolean) => void;
  save: () => Promise<void>;
}) {
  return (
    <form
      className="panel settings-form"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <Settings2 size={26} />
      <h3>Workspace preferences</h3>
      <label htmlFor="workspace-name">Display name</label>
      <input
        id="workspace-name"
        value={settings.name}
        maxLength={100}
        onChange={(e) => {
          setSaved(false);
          setSettings({ ...settings, name: e.target.value });
        }}
        required
      />
      <label htmlFor="timezone">Time zone</label>
      <select
        id="timezone"
        value={settings.timezone}
        onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
      >
        {[
          "Asia/Kolkata",
          "UTC",
          "America/New_York",
          "America/Los_Angeles",
          "Europe/London",
          "Europe/Paris",
          "Asia/Singapore",
          "Australia/Sydney",
        ].map((zone) => (
          <option key={zone}>{zone}</option>
        ))}
      </select>
      <label htmlFor="retention">Data retention (days)</label>
      <input
        id="retention"
        type="number"
        min="1"
        max="365"
        value={settings.retention_days}
        onChange={(e) =>
          setSettings({
            ...settings,
            retention_days: Number(e.target.value),
          })
        }
      />
      <p className="field-note">
        Expired event history is pruned when planning a new event. Active or
        uncertain actions keep their evidence until reconciled. Audit records
        are retained separately; use the data controls below to erase local
        records.
      </p>
      <button className="button primary" type="submit">
        {saved ? (
          <>
            <Check size={16} />
            Saved
          </>
        ) : (
          "Save preferences"
        )}
      </button>
    </form>
  );
}
