import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { DEFAULT_REDIRECT } from "../config";
import { authApi } from "../lib/api";
import { getErrorMessage } from "../lib/errors";
import { useAuthStore } from "../store/auth";

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setTokens = useAuthStore((state) => state.setTokens);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const registered = searchParams.get("registered") === "1";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setSubmitting(true);
    try {
      const token = await authApi.login({ email, password });
      setTokens(token);
      const redirect = searchParams.get("redirect");
      navigate(redirect || DEFAULT_REDIRECT, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, "Login failed."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="card">
      <h1>Welcome back</h1>
      <p className="subtitle">Log in to your Attlytics account</p>

      {registered && (
        <div className="alert success">Account created. Please log in.</div>
      )}
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" disabled={submitting}>
          {submitting ? "Logging in\u2026" : "Log in"}
        </button>
      </form>

      <div className="row">
        <span className="muted">Don&apos;t have an account?</span>
        <Link to="/register">Create one</Link>
      </div>
    </main>
  );
}
