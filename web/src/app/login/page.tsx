"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { setWebAuth } from "@/lib/auth";

export default function LoginPage() {
  const [token, setToken] = useState("");
  const router = useRouter();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    setWebAuth(token);
    router.push("/overview");
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
        <button type="submit">Continue</button>
      </form>
    </main>
  );
}
