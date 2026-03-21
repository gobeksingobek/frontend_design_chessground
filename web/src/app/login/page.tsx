"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { BodyText, CardTitle, CaptionText, FieldLabel, MonoText, MutedText, PageTitle } from "@/components/ui/typography";
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
      <form onSubmit={onSubmit} className="w-full max-w-2xl">
        <Card className="gap-6">
          <div className="grid gap-3">
            <CaptionText>ChessGround Web</CaptionText>
            <PageTitle>Sign in to the analysis workspace</PageTitle>
            <MutedText>Enter your backend API bearer token to validate access and continue into the dashboard.</MutedText>
          </div>
          <label className="grid gap-2">
            <FieldLabel as="span">API token</FieldLabel>
            <Input placeholder="API token" value={token} onChange={(e) => setToken(e.target.value)} aria-label="API token" />
          </label>
          <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary" disabled={isSubmitting}>{isSubmitting ? "Validating…" : "Continue"}</Button><Button type="button" onClick={onLogout}>Log out / clear stored token</Button></div>
          <Suspense fallback={null}><LoginReasonNotice /></Suspense>
          {message ? <BodyText className="font-medium text-success">{message}</BodyText> : null}
          {error ? <BodyText className="font-medium text-warning">{error}</BodyText> : null}
          <Card className="gap-4 border-border/80 bg-panel-muted">
            <div className="grid gap-1">
              <CardTitle>Current API diagnostics</CardTitle>
              <MutedText>Use these values to confirm which backend endpoint and token source the browser is using.</MutedText>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="grid gap-1"><FieldLabel as="span">Base URL</FieldLabel><MonoText className="break-all">{diagnostics.apiBaseUrl}</MonoText></div>
              <div className="grid gap-1"><FieldLabel as="span">Token source</FieldLabel><BodyText>{diagnostics.tokenSource}</BodyText></div>
              <div className="grid gap-1"><FieldLabel as="span">Stored token</FieldLabel><BodyText>{hasStoredToken ? "present" : "missing"}</BodyText></div>
            </div>
          </Card>
        </Card>
      </form>
    </main>
  );
}

function LoginReasonNotice() {
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");
  if (reason === "unauthorized") return <BodyText className="font-medium text-warning">Session expired due to unauthorized API response.</BodyText>;
  if (reason === "unauthorized_repeated") return <BodyText className="font-medium text-warning">Multiple unauthorized responses detected. Please log in again.</BodyText>;
  return null;
}
