"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { getWebToken, setWebAuth } from "@/lib/auth";
import { getAuthDiagnostics, validateApiToken } from "@/lib/api-client";

export default function LoginPage() {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();
  const diagnostics = useMemo(() => getAuthDiagnostics(), []);
  const hasStoredToken = Boolean(getWebToken());

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    setMessage(null);
    setError(null);
    setIsSubmitting(true);
    setWebAuth(token);
    try {
      await validateApiToken();
      setMessage("Token validated. Redirecting…");
      router.push("/overview");
    } catch (err) {
      setWebAuth(null);
      setError(err instanceof Error ? err.message : "Unable to validate token.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function onLogout() {
    setWebAuth(null);
    setMessage("Stored token cleared.");
    setError(null);
    setToken("");
  }

  return (
    <main className="login">
      <form onSubmit={onSubmit} className="card">
        <h1>ChessGround Web</h1>
        <p>Enter your backend API bearer token to continue.</p>
        <input
          placeholder="API token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          aria-label="API token"
        />
        <button type="submit" disabled={isSubmitting}>{isSubmitting ? "Validating…" : "Continue"}</button>
        <button type="button" onClick={onLogout}>Log out / clear stored token</button>
        <Suspense fallback={null}>
          <LoginReasonNotice />
        </Suspense>
        {message ? <p className="ok">{message}</p> : null}
        {error ? <p className="warn">{error}</p> : null}
        <section className="card diagnostics-panel">
          <h2>Current API diagnostics</h2>
          <p><strong>Base URL:</strong> <code>{diagnostics.apiBaseUrl}</code></p>
          <p><strong>Token source:</strong> {diagnostics.tokenSource}</p>
          <p><strong>Stored token:</strong> {hasStoredToken ? "present" : "missing"}</p>
        </section>
      </form>
    </main>
  );
}

function LoginReasonNotice() {
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");

  if (reason === "unauthorized") {
    return <p className="warn">Session expired due to unauthorized API response.</p>;
  }

  if (reason === "unauthorized_repeated") {
    return <p className="warn">Multiple unauthorized responses detected. Please log in again.</p>;
  }

  return null;
}
