"use client";

import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

const AUTH_KEY = "cg_web_authed";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const authed = window.localStorage.getItem(AUTH_KEY);
    if (authed !== "true") {
      router.replace("/login");
    }
  }, [router]);

  return <>{children}</>;
}

export function setWebAuth(value: boolean) {
  if (value) {
    window.localStorage.setItem(AUTH_KEY, "true");
    return;
  }
  window.localStorage.removeItem(AUTH_KEY);
}
