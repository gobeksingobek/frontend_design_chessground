"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const navItems = [
  { href: "/overview", label: "Overview" },
  { href: "/analysis", label: "Analysis" },
  { href: "/tree", label: "Tree" },
  { href: "/trainer", label: "Trainer" },
  { href: "/games", label: "Games" },
  { href: "/lines", label: "Lines" },
  { href: "/time-usage", label: "Time usage" },
  { href: "/rating-bands", label: "Rating bands" },
  { href: "/insights", label: "Insights" },
  { href: "/review", label: "Review" },
  { href: "/sidelines", label: "Sidelines" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="shell">
      <aside className="sidebar">
        <h1>ChessGround</h1>
        <nav>
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className={pathname === item.href ? "active" : ""}>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>Web App</div>
          <Link href="/login">Switch user</Link>
        </header>
        <section>{children}</section>
      </main>
    </div>
  );
}
