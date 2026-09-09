import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { deviceApi } from "../lib/api";
import { getErrorMessage } from "../lib/errors";
import { decodeJwt } from "../lib/jwt";
import type { EnrollTokenPayload } from "../types/device";


export function DeviceRegisterPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState<{ text: string; kind: "ok" | "err" } | null>(
    null,
  );

  async function onConfirm() {
    if (!token || confirming) return;
    setConfirming(true);
    setMessage(null);
    try {
      const result = await deviceApi.confirmEnrollment(token);
      setMessage({ text: result.detail, kind: "ok" });
    } catch (err) {
      setMessage({
        text: getErrorMessage(err, "Could not confirm this device."),
        kind: "err",
      });
    } finally {
      setConfirming(false);
    }
  }

  if (!token) {
    return (
      <main className="card">
        <h1>Missing enrollment token</h1>
        <p className="subtitle">
          This link is invalid. Please run &ldquo;Connect account&rdquo; in the
          agent again.
        </p>
        <Link to="/">Go home</Link>
      </main>
    );
  }

  const payload = decodeJwt<EnrollTokenPayload>(token);
  if (!payload) {
    return (
      <main className="card">
        <h1>Invalid enrollment token</h1>
        <p className="subtitle">
          The token could not be read. Try connecting again from the agent.
        </p>
        <Link to="/">Go home</Link>
      </main>
    );
  }

  return (
    <main className="card">
      <h1>Register this device</h1>
      <p className="subtitle">
        Confirm that you want to link this computer to your account.
      </p>

      {message && (
        <div className={`alert ${message.kind === "ok" ? "success" : "error"}`}>
          {message.text}
        </div>
      )}

      <dl className="device-info">
        <dt>Device</dt>
        <dd>{payload.device_name ?? "Unknown"}</dd>
        <dt>Type</dt>
        <dd>{payload.device_type ?? "Unknown"}</dd>
        <dt>Hostname</dt>
        <dd>{payload.hostname ?? "Unknown"}</dd>
        <dt>Platform</dt>
        <dd>{payload.platform ?? "Unknown"}</dd>
        <dt>Installation</dt>
        <dd className="mono">
          {(payload.sub ?? payload.installation_id ?? "").slice(0, 8)}
          {"\u2026"}
        </dd>
      </dl>

      <button
        type="button"
        onClick={onConfirm}
        disabled={confirming || message?.kind === "ok"}
      >
        {confirming ? "Confirming\u2026" : "Confirm device"}
      </button>
      <p className="muted" style={{ marginTop: "0.8rem" }}>
        Confirming links this device to your account and sends the API key back
        to the agent over a secure connection.
      </p>
    </main>
  );
}

