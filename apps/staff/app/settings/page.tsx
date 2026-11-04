"use client";

import { useState } from "react";
import { Shell } from "../../components/Shell";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../lib/api";

type Setting = Schemas["SettingOut"];

export default function SettingsPage() {
  return (
    <Shell>
      <Settings />
    </Shell>
  );
}

const loadSettings = () => call(() => api.GET("/api/v1/staff/settings"));

function Settings() {
  const { data: rows = [], error, reload } = useApiData(loadSettings);
  const onSaved = async () => reload();

  return (
    <>
      <h1 className={ui.title}>Settings</h1>
      {error && <p className={ui.error}>{error}</p>}
      {rows.map((row) => (
        <SettingRow key={row.key} setting={row} onSaved={onSaved} />
      ))}
    </>
  );
}

function money(value: unknown): string {
  if (value && typeof value === "object" && "amount" in value)
    return String((value as { amount: string }).amount);
  return "";
}

function SettingRow({ setting, onSaved }: { setting: Setting; onSaved: () => Promise<void> }) {
  const isMoney = setting.key === "refunds.dual_approval_threshold";
  const [text, setText] = useState(isMoney ? money(setting.value) : String(setting.value ?? ""));
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const save = async () => {
    setMessage(null);
    const value = isMoney ? (text.trim() ? { amount: text.trim(), currency: "PKR" } : null) : text;
    try {
      await call(() =>
        api.PUT("/api/v1/staff/settings/{key}", {
          params: { path: { key: setting.key } },
          body: { value },
        }),
      );
      setMessage({ ok: true, text: "Saved." });
      await onSaved();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <section className={ui.panel}>
      <h2 className={ui.subtitle}>{setting.description}</h2>
      <p className={ui.muted}>
        {setting.group === "security" ? "Security setting (Owner only)." : "Store setting."}
        {isMoney &&
          " Leave empty for “not set yet”: until an amount is set, every refund needs a second approver."}
      </p>
      <div className={ui.row}>
        {isMoney && <span>PKR</span>}
        <input
          className={ui.input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={!setting.editable}
          inputMode={isMoney ? "decimal" : "text"}
          aria-label={setting.description}
        />
        {setting.editable && (
          <button className={ui.secondary} onClick={() => void save()}>
            Save
          </button>
        )}
      </div>
      {message && <p className={message.ok ? ui.success : ui.error}>{message.text}</p>}
    </section>
  );
}
