"use client";

import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { getWebToken, isAuthed } from "@/lib/auth";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthed() || !getWebToken()) {
      router.replace("/login");
    }
  }, [router]);

  return <>{children}</>;
}
