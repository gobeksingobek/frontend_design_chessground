"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
  async function onSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!token.trim()) return; setMessage(null); setError(null); setIsSubmitting(true); setWebAuth(token); try { await validateApiToken(); setMessage("Token validated. Redirecting…"); router.push("/overview"); } catch (err) { setWebAuth(null); setError(err instanceof Error ? err.message : "Unable to validate token."); } finally { setIsSubmitting(false); } }
  function onLogout() { setWebAuth(null); setMessage("Stored token cleared."); setError(null); setToken(""); }
  return (
    <main className="grid min-h-screen place-items-center bg-bg px-6 py-10 text-text">
      <form onSubmit={onSubmit} className="w-full max-w-xl">
        <Card>
          <h1 className="text-2xl font-bold">ChessGround Web</h1>
          <p className="text-sm text-text-muted">Enter your backend API bearer token to continue.</p>
          <Input placeholder="API token" value={token} onChange={(e) => setToken(e.target.value)} aria-label="API token" />
          <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary" disabled={isSubmitting}>{isSubmitting ? "Validating…" : "Continue"}</Button><Button type="button" onClick={onLogout}>Log out / clear stored token</Button></div>
          <Suspense fallback={null}><LoginReasonNotice /></Suspense>
          {message ? <p className="text-sm text-success">{message}</p> : null}
          {error ? <p className="text-sm text-warning">{error}</p> : null}
          <Card className="border-border/80 bg-panel-muted"><h2 className="text-base font-semibold">Current API diagnostics</h2><p><strong>Base URL:</strong> <code>{diagnostics.apiBaseUrl}</code></p><p><strong>Token source:</strong> {diagnostics.tokenSource}</p><p><strong>Stored token:</strong> {hasStoredToken ? "present" : "missing"}</p></Card>
        </Card>
      </form>
    </main>
  );
}

function LoginReasonNotice() {
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");
  if (reason === "unauthorized") return <p className="text-sm text-warning">Session expired due to unauthorized API response.</p>;
  if (reason === "unauthorized_repeated") return <p className="text-sm text-warning">Multiple unauthorized responses detected. Please log in again.</p>;
  return null;
}
