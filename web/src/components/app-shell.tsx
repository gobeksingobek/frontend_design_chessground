"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { setWebAuth } from "@/lib/auth";

const navItems = [
  { href: "/overview", label: "Overview" },
  { href: "/analysis", label: "Analysis" },
  { href: "/settings", label: "Settings" },
  { href: "/tree", label: "Tree" },
  { href: "/trainer", label: "Trainer" },
  { href: "/games", label: "Games" },
  { href: "/lines", label: "Lines" },
  { href: "/time-usage", label: "Time usage" },
  { href: "/rating-bands", label: "Rating bands" },
  { href: "/insights", label: "Insights" },
  { href: "/review", label: "Review" },
  { href: "/sidelines", label: "Sidelines" },
  { href: "/repertoires", label: "Repertoires" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  function onLogout() {
    setWebAuth(null);
  }

  return (
    <div className="grid min-h-screen bg-bg text-text lg:grid-cols-shell">
      <aside className="border-b border-border bg-[#0b1428] px-xl py-2xl lg:border-b-0 lg:border-r">
        <div className="sticky top-0 grid gap-6">
          <div className="grid gap-2">
            <h1 className="text-2xl font-bold">ChessGround</h1>
            <p className="text-sm text-text-muted">Analysis, repertoire, and training workflows in one place.</p>
          </div>
          <nav className="grid gap-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-lg px-3 py-2 text-sm font-medium text-text-muted transition hover:bg-panel-elevated hover:text-text",
                  pathname === item.href && "bg-panel-elevated text-text shadow-soft",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </aside>
      <main className="px-lg py-xl sm:px-xl lg:px-2xl">
        <header className="mb-xl flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-panel px-xl py-lg shadow-soft">
          <div>
            <p className="text-sm font-medium text-text-subtle">ChessGround Web</p>
            <p className="text-xs text-text-muted">Consistent Tailwind primitives and shared tokens.</p>
          </div>
          <Link href="/login" onClick={onLogout}>
            <Button variant="ghost">Log out / switch user</Button>
          </Link>
        </header>
        <section className="grid gap-4">{children}</section>
      </main>
    </div>
  );
}
