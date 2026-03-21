"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormField } from "@/components/ui/form-field";
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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) {
      setError("Enter an API token before continuing.");
      return;
    }
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
    <main className="grid min-h-screen place-items-center px-6 py-10">
      <form onSubmit={onSubmit} className="w-full max-w-3xl">
        <Card className="gap-6 overflow-hidden border-border/70 bg-card/95">
          <div className="grid gap-3">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-primary">
              <span className="h-2 w-2 rounded-full bg-primary" />
              ChessGround Web
            </div>
            <PageTitle>Sign in to the analysis workspace</PageTitle>
            <MutedText>Enter your backend API bearer token to validate access and continue into the dashboard.</MutedText>
          </div>
          <FormField label="API token" htmlFor="api-token" required helpText="Paste the backend bearer token exactly as issued. It is stored locally in the browser for this workspace.">
            <Input id="api-token" placeholder="sk_live_..." value={token} onChange={(e) => setToken(e.target.value)} aria-invalid={Boolean(error && !token.trim())} />
          </FormField>
          <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary" disabled={isSubmitting}>{isSubmitting ? "Validating…" : "Continue"}</Button><Button type="button" variant="ghost" onClick={onLogout}>Clear stored token</Button></div>
          <Suspense fallback={null}><LoginReasonNotice /></Suspense>
          {message ? <BodyText className="font-medium text-success">{message}</BodyText> : null}
          {error ? <BodyText className="font-medium text-warning">{error}</BodyText> : null}
          <Card className="gap-4 border-border/80 bg-elevated/80">
            <div className="grid gap-1">
              <CardTitle>Current API diagnostics</CardTitle>
              <MutedText>Use these values to confirm which backend endpoint and token source the browser is using.</MutedText>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="grid gap-1"><FieldLabel as="span">Base URL</FieldLabel><MonoText className="break-all">{diagnostics.apiBaseUrl}</MonoText></div>
              <div className="grid gap-1"><FieldLabel as="span">Token source</FieldLabel><BodyText>{diagnostics.tokenSource}</BodyText></div>
              <div className="grid gap-2"><FieldLabel as="span">Stored token</FieldLabel><Badge tone={hasStoredToken ? "success" : "warning"}>{hasStoredToken ? "present" : "missing"}</Badge></div>
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
