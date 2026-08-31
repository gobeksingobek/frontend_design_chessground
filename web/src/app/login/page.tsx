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
    <main className="grid min-h-screen place-items-center px-4 py-8 sm:px-6">
      <form onSubmit={onSubmit} className="w-full max-w-5xl">
        <Card variant="glass" className="gap-0 overflow-hidden p-0 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <section className="grid content-between gap-8 border-b border-border/35 bg-muted/55 p-6 md:border-b-0 md:border-r md:p-8">
            <div className="grid gap-5">
              <div className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-primary">
                <span className="h-2 w-2 rounded-full bg-primary" />
                ChessGround
              </div>
              <div className="grid gap-3">
                <PageTitle className="text-3xl">Your repertoire, in focus.</PageTitle>
                <MutedText>Analyze positions, review games, and train the lines that matter from one durable workspace.</MutedText>
              </div>
            </div>
            <div className="grid gap-3 border-t border-border/35 pt-5">
              <CaptionText>Connection</CaptionText>
              <div className="grid gap-1"><FieldLabel as="span">Base URL</FieldLabel><MonoText className="break-all">{diagnostics.apiBaseUrl}</MonoText></div>
              <div className="grid gap-1"><FieldLabel as="span">Token source</FieldLabel><BodyText>{diagnostics.tokenSource}</BodyText></div>
              <div className="flex items-center justify-between gap-3"><FieldLabel as="span">Stored token</FieldLabel><Badge tone={hasStoredToken ? "success" : "warning"}>{hasStoredToken ? "present" : "missing"}</Badge></div>
            </div>
          </section>
          <section className="grid content-center gap-6 bg-card p-6 sm:p-8 md:p-10">
            <div className="grid gap-2">
              <CardTitle className="text-xl">Sign in to the analysis workspace</CardTitle>
              <MutedText>Enter your backend bearer token to validate this browser session.</MutedText>
            </div>
            <FormField label="API token" htmlFor="api-token" required helpText="Stored locally in this browser and sent only to the configured ChessGround backend.">
              <Input id="api-token" type="password" autoComplete="current-password" placeholder="Paste your API token" value={token} onChange={(e) => setToken(e.target.value)} aria-invalid={Boolean(error && !token.trim())} />
            </FormField>
            <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary" disabled={isSubmitting}>{isSubmitting ? "Validating…" : "Continue"}</Button><Button type="button" variant="ghost" onClick={onLogout}>Clear stored token</Button></div>
            <Suspense fallback={null}><LoginReasonNotice /></Suspense>
            {message ? <BodyText className="rounded-control border border-success/25 bg-success/10 px-3 py-2 font-medium text-success">{message}</BodyText> : null}
            {error ? <BodyText className="rounded-control border border-danger/25 bg-danger/10 px-3 py-2 font-medium text-danger">{error}</BodyText> : null}
          </section>
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
