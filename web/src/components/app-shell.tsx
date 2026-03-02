"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const navItems = [
  { href: "/overview", label: "Overview" },
  { href: "/analysis", label: "Analysis" },
  { href: "/games", label: "Games" },
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
          <div>Web Phase 1 Shell</div>
          <Link href="/login">Switch user</Link>
        </header>
        <section>{children}</section>
      </main>
    </div>
  );
}
