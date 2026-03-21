"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { useTheme } from "@/components/theme-provider";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { setWebAuth } from "@/lib/auth";

type NavItem = {
  href: string;
  label: string;
  icon: (props: { className?: string }) => ReactNode;
  match?: (pathname: string) => boolean;
};

type NavSection = {
  label: string;
  items: NavItem[];
};

type DashboardPageConfig = {
  title?: string;
  description?: string;
  actions?: ReactNode;
};

type DashboardPageContextValue = {
  page: DashboardPageConfig;
  setPage: (next: DashboardPageConfig) => void;
};

const DashboardPageContext = createContext<DashboardPageContextValue | null>(null);

const navSections: NavSection[] = [
  {
    label: "Analysis",
    items: [
      { href: "/overview", label: "Overview", icon: GridIcon },
      { href: "/analysis", label: "Board analysis", icon: ActivityIcon },
      { href: "/games", label: "Games", icon: GamepadIcon, match: (pathname) => pathname.startsWith("/games") },
      { href: "/insights", label: "Insights", icon: SparklesIcon },
      { href: "/sidelines", label: "Sidelines", icon: BranchIcon },
      { href: "/tree", label: "Explorer tree", icon: TreeIcon },
    ],
  },
  {
    label: "Training",
    items: [
      { href: "/trainer", label: "Trainer", icon: TargetIcon },
      { href: "/review", label: "Review queue", icon: RefreshIcon },
      { href: "/time-usage", label: "Time usage", icon: ClockIcon },
      { href: "/rating-bands", label: "Rating bands", icon: BarChartIcon },
    ],
  },
  {
    label: "Repertoire",
    items: [
      { href: "/repertoires", label: "Imports", icon: FolderIcon },
      { href: "/lines", label: "Lines", icon: BookIcon },
    ],
  },
  {
    label: "Settings",
    items: [{ href: "/settings", label: "Runtime settings", icon: SettingsIcon }],
  },
];

const pageFallbacks = new Map<string, DashboardPageConfig>([
  ["/overview", { title: "Overview", description: "Status, recent activity, and quick actions for your analysis workspace." }],
  ["/analysis", { title: "Board Analysis", description: "Inspect positions, run local evaluation, and create sidelines." }],
  ["/games", { title: "Games", description: "Browse recent games and drill into move-level detail." }],
  ["/insights", { title: "Insights", description: "Review generated findings and supporting evidence." }],
  ["/lines", { title: "Lines", description: "Track line-level aggregate performance and coverage." }],
  ["/rating-bands", { title: "Rating Bands", description: "Compare performance by opponent strength segments." }],
  ["/repertoires", { title: "Repertoire", description: "Import and monitor opening repertoire files." }],
  ["/review", { title: "Review", description: "Work through deviations and coverage gaps in one queue." }],
  ["/settings", { title: "Settings", description: "Tune fetching, engine, path, and player profile options." }],
  ["/sidelines", { title: "Sidelines", description: "Monitor queued sideline analysis jobs from the backend." }],
  ["/time-usage", { title: "Time Usage", description: "Understand in-book and out-of-book time patterns." }],
  ["/trainer", { title: "Trainer", description: "Start practice sessions and manage spaced-repetition flow." }],
  ["/tree", { title: "Tree Explorer", description: "Navigate branch structure, coverage, and move metrics." }],
]);

function getFallbackPage(pathname: string): DashboardPageConfig {
  if (pathname.startsWith("/games/")) {
    const gameId = pathname.split("/").filter(Boolean).at(-1);
    return {
      title: gameId ? `Game ${gameId}` : "Game Detail",
      description: "Inspect move quality, evaluation swings, and sideline opportunities.",
    };
  }
  return pageFallbacks.get(pathname) ?? { title: "ChessGround", description: "Analysis, repertoire, and training workflows in one place." };
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [page, setPage] = useState<DashboardPageConfig>({});
  const fallbackPage = useMemo(() => getFallbackPage(pathname), [pathname]);
  const resolvedPage = {
    title: page.title ?? fallbackPage.title,
    description: page.description ?? fallbackPage.description,
    actions: page.actions,
  };

  useEffect(() => {
    setMobileMenuOpen(false);
    setPage({});
  }, [pathname]);

  function onLogout() {
    setWebAuth(null);
  }

  return (
    <DashboardPageContext.Provider value={{ page: resolvedPage, setPage }}>
      <DashboardShell>
        <DashboardSidebar
          collapsed={sidebarCollapsed}
          mobileOpen={mobileMenuOpen}
          onCollapseToggle={() => setSidebarCollapsed((current) => !current)}
          onMobileClose={() => setMobileMenuOpen(false)}
        />
        <div className="min-w-0 flex-1">
          <DashboardHeader
            title={resolvedPage.title}
            description={resolvedPage.description}
            actions={resolvedPage.actions}
            onMobileMenuToggle={() => setMobileMenuOpen((current) => !current)}
            onLogout={onLogout}
          />
          <main className="min-w-0 px-page-pad py-xl sm:px-xl lg:px-page-pad-lg lg:py-2xl">
            <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-page-gap">{children}</div>
          </main>
        </div>
      </DashboardShell>
    </DashboardPageContext.Provider>
  );
}

export function DashboardShell({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-background text-foreground lg:flex">{children}</div>;
}

export function DashboardSidebar({
  collapsed,
  mobileOpen,
  onCollapseToggle,
  onMobileClose,
}: {
  collapsed: boolean;
  mobileOpen: boolean;
  onCollapseToggle: () => void;
  onMobileClose: () => void;
}) {
  const pathname = usePathname();
  const sidebar = (
    <div
      className={cn(
        "flex h-full flex-col border-border bg-elevated text-foreground shadow-panel",
        collapsed ? "w-[5.5rem]" : "w-72",
      )}
    >
      <div className="flex items-center justify-between gap-3 border-b border-border/80 px-4 py-4">
        <Link href="/overview" className="flex min-w-0 items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/15 text-primary ring-1 ring-inset ring-primary/25">
            <KnightIcon className="h-6 w-6" />
          </div>
          {!collapsed ? (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold uppercase tracking-[0.2em] text-primary/80">ChessGround</p>
              <p className="truncate text-xs text-muted-foreground">Analysis workspace</p>
            </div>
          ) : null}
        </Link>
        <button
          type="button"
          onClick={onCollapseToggle}
          className="hidden rounded-md border border-border/70 bg-card/80 p-2 text-muted-foreground transition hover:bg-overlay hover:text-foreground lg:inline-flex"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <PanelIcon className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <nav className="grid gap-6">
          {navSections.map((section) => (
            <div key={section.label} className="grid gap-2">
              <p className={cn("px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/70", collapsed && "px-0 text-center")}>{collapsed ? section.label.slice(0, 1) : section.label}</p>
              <div className="grid gap-1">
                {section.items.map((item) => {
                  const active = item.match ? item.match(pathname) : pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onMobileClose}
                      className={cn(
                        "group relative flex items-center gap-3 overflow-hidden rounded-xl border border-transparent px-3 py-2.5 text-sm font-medium text-muted-foreground transition hover:border-border/70 hover:bg-hover hover:text-hover-foreground",
                        collapsed && "justify-center px-2",
                        active && "border-primary/25 bg-selection text-selection-foreground shadow-soft",
                      )}
                      aria-current={active ? "page" : undefined}
                    >
                      <span className={cn("absolute inset-y-2 left-0 w-1 rounded-r-full bg-primary opacity-0 transition", active && "opacity-100", collapsed && "inset-x-2 inset-y-auto bottom-0 left-2 h-1 w-auto rounded-t-full rounded-r-none")} />
                      <span className={cn("text-muted-foreground transition group-hover:text-primary", active && "text-primary")}>
                        {item.icon({ className: "h-5 w-5" })}
                      </span>
                      {!collapsed ? <span className="truncate">{item.label}</span> : null}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>
    </div>
  );

  return (
    <>
      <aside className="sticky top-0 hidden h-screen shrink-0 border-r border-border/80 lg:block">{sidebar}</aside>
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button type="button" className="absolute inset-0 bg-background/70 backdrop-blur-sm" onClick={onMobileClose} aria-label="Close navigation" />
          <div className="absolute inset-y-0 left-0 max-w-[85vw]">{sidebar}</div>
        </div>
      ) : null}
    </>
  );
}

export function DashboardHeader({
  title,
  description,
  actions,
  onMobileMenuToggle,
  onLogout,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  onMobileMenuToggle: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-background/90 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <button
              type="button"
              onClick={onMobileMenuToggle}
              className="inline-flex rounded-xl border border-border/80 bg-card px-3 py-2 text-muted-foreground shadow-soft transition hover:bg-overlay hover:text-foreground lg:hidden"
              aria-label="Open navigation"
            >
              <MenuIcon className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/80">Dashboard</p>
              <h1 className="truncate text-2xl font-semibold text-foreground sm:text-3xl">{title}</h1>
              {description ? <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {actions}
            <ThemeToggle />
            <Link href="/login" onClick={onLogout}>
              <Button variant="ghost" className="bg-card/80">Log out</Button>
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}


function ThemeToggle() {
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <Button
      type="button"
      variant="ghost"
      className="bg-card/80"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      aria-pressed={isDark}
    >
      <span aria-hidden="true">{isDark ? "☀️" : "🌙"}</span>
      {isDark ? "Light mode" : "Dark mode"}
    </Button>
  );
}

export function PageContainer({
  title,
  description,
  actions,
  children,
}: DashboardPageConfig & { children: ReactNode }) {
  const context = useContext(DashboardPageContext);

  useEffect(() => {
    context?.setPage({ title, description, actions });
    return () => context?.setPage({});
  }, [actions, context, description, title]);

  return <div className="grid gap-page-gap">{children}</div>;
}

export function PageSection({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("grid gap-section-gap", className)}>{children}</section>;
}

function IconWrapper({ className, children }: { className?: string; children: ReactNode }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>{children}</svg>;
}

function GridIcon({ className }: { className?: string }) { return <IconWrapper className={className}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></IconWrapper>; }
function ActivityIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M4 12h4l2.5-5 3 10L16 12h4" /></IconWrapper>; }
function GamepadIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M7 10h10a4 4 0 0 1 3.6 5.8l-1.3 2.6a2 2 0 0 1-3 .7l-2.3-1.7H10l-2.3 1.7a2 2 0 0 1-3-.7l-1.3-2.6A4 4 0 0 1 7 10Z" /><path d="M8 13v3" /><path d="M6.5 14.5h3" /><circle cx="16.5" cy="14.5" r=".75" /><circle cx="18.5" cy="12.5" r=".75" /></IconWrapper>; }
function SparklesIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z" /><path d="M5 18l.7 1.8L7.5 21l-1.8.7L5 23l-.7-1.3L2.5 21l1.8-1.2L5 18Z" /><path d="m19 15 .8 2.1L22 18l-2.2.9L19 21l-.8-2.1L16 18l2.2-.9L19 15Z" /></IconWrapper>; }
function BranchIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M7 6a2 2 0 1 1 0 4 2 2 0 0 1 0-4Zm0 0v10a2 2 0 1 0 2 2h4a2 2 0 1 0 0-2H9" /><path d="M9 8h6a2 2 0 1 0 0-2" /></IconWrapper>; }
function TreeIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M12 4v16" /><path d="M12 8h6" /><path d="M12 14h-6" /><circle cx="18" cy="8" r="2" /><circle cx="6" cy="14" r="2" /><circle cx="12" cy="4" r="2" /><circle cx="12" cy="20" r="2" /></IconWrapper>; }
function TargetIcon({ className }: { className?: string }) { return <IconWrapper className={className}><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></IconWrapper>; }
function RefreshIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3" /><path d="M4 4v5h5M20 20v-5h-5" /></IconWrapper>; }
function ClockIcon({ className }: { className?: string }) { return <IconWrapper className={className}><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></IconWrapper>; }
function BarChartIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M4 20h16" /><path d="M7 17V9" /><path d="M12 17V5" /><path d="M17 17v-6" /></IconWrapper>; }
function FolderIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M3 8.5A2.5 2.5 0 0 1 5.5 6H10l2 2h6.5A2.5 2.5 0 0 1 21 10.5v7A2.5 2.5 0 0 1 18.5 20h-13A2.5 2.5 0 0 1 3 17.5v-9Z" /></IconWrapper>; }
function BookIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v16H7.5A2.5 2.5 0 0 0 5 21V5.5Z" /><path d="M5 18.5A2.5 2.5 0 0 1 7.5 16H19" /></IconWrapper>; }
function SettingsIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M12 8.5A3.5 3.5 0 1 0 12 15.5A3.5 3.5 0 1 0 12 8.5Z" /><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.7-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.7 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2H9a1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .7.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1V9c0 .4.2.7.6.9h.2a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.7Z" /></IconWrapper>; }
function KnightIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M8 19h9" /><path d="M8 19c.3-3.2 1.5-5 4-6l1-4-2-2c1.2-1.8 3.3-2.7 5.5-2.5-.8 1-1 2.4-.5 3.6 1.4.8 2.2 2.2 2 3.9-.2 2.7-2.7 4.3-5.2 5.2" /><circle cx="14.5" cy="8.5" r=".75" /></IconWrapper>; }
function PanelIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M4 5h16v14H4z" /><path d="M9 5v14" /></IconWrapper>; }
function MenuIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M4 7h16M4 12h16M4 17h16" /></IconWrapper>; }
