"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { setWebAuth } from "@/components/auth-gate";

export default function LoginPage() {
  const [token, setToken] = useState("");
  const router = useRouter();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    setWebAuth(true);
    window.localStorage.setItem("cg_web_token_hint", token.trim());
    router.push("/overview");
  }

  return (
    <main className="login">
      <form onSubmit={onSubmit} className="card">
        <h1>ChessGround Web</h1>
        <p>Phase 1 auth gate placeholder. Enter any token to continue.</p>
        <input
          placeholder="API token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          aria-label="API token"
        />
        <button type="submit">Continue</button>
      </form>
    </main>
  );
}
