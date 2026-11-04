"use client";

import ui from "./ui.module.css";

export interface PendingDevice {
  email: string;
  secret: string;
  otpauth_uri: string;
  qr_svg: string;
}

/** QR code (rendered by the API, never by a third party) plus the secret for manual entry. */
export function AuthenticatorQr({ device }: { device: PendingDevice }) {
  const src = `data:image/svg+xml;utf8,${encodeURIComponent(device.qr_svg)}`;
  return (
    <div>
      {/* eslint-disable-next-line @next/next/no-img-element -- an inline data URI, not a remote image */}
      <img className={ui.qr} src={src} alt="QR code for your authenticator app" />
      <p className={`${ui.muted} ${ui.center}`}>
        Scan with an authenticator app, or enter this key:
      </p>
      <p className={ui.secret} data-testid="totp-secret">
        {device.secret}
      </p>
    </div>
  );
}

export function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  return (
    <div>
      <h2 className={ui.subtitle}>Save your recovery codes</h2>
      <p className={ui.muted}>
        Each code works once if you lose your authenticator app. Store them offline, somewhere safe.
        They won&apos;t be shown again.
      </p>
      <ul className={ui.codes} data-testid="recovery-codes">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <button className={ui.button} onClick={onDone}>
        I&apos;ve saved them
      </button>
    </div>
  );
}

export function CodeField({
  value,
  onChange,
  label = "Authenticator code",
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
}) {
  return (
    <label className={ui.field}>
      {label}
      <input
        className={ui.codeInput}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
        required
      />
    </label>
  );
}
