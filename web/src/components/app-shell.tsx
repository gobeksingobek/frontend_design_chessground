"use client";

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
  groups: Array<{
    label: string;
    items: NavItem[];
  }>;
};

type DashboardPageConfig = {
  title?: string;
  description?: string;
  actions?: ReactNode;
};

type DashboardContentGridProps = {
  children: ReactNode;
  utility?: ReactNode;
  className?: string;
  workspaceClassName?: string;
  utilityClassName?: string;
};

type DashboardPageContextValue = {
  page: DashboardPageConfig;
  setPage: (next: DashboardPageConfig) => void;
};

const DashboardPageContext = createContext<DashboardPageContextValue | null>(null);

const navSections: NavSection[] = [
  {
    label: "Analysis",
    groups: [
      {
        label: "Workspace",
        items: [
          { href: "/overview", label: "Overview", icon: GridIcon },
          { href: "/analysis", label: "Analysis", icon: ActivityIcon },
          { href: "/games", label: "Games", icon: GamepadIcon, match: (pathname) => pathname.startsWith("/games") },
          { href: "/tree", label: "Tree", icon: TreeIcon },
          { href: "/trainer", label: "Trainer", icon: TargetIcon },
        ],
      },
      {
        label: "Reports",
        items: [
          { href: "/lines", label: "Lines", icon: BranchIcon },
          { href: "/time-usage", label: "Time usage", icon: ClockIcon },
          { href: "/rating-bands", label: "Rating bands", icon: BarChartIcon },
          { href: "/insights", label: "Insights", icon: SparklesIcon },
          { href: "/review", label: "Review", icon: BookIcon },
        ],
      },
      {
        label: "Data",
        items: [
          { href: "/repertoires", label: "Repertoires", icon: FolderIcon },
          { href: "/sidelines", label: "Sidelines", icon: RefreshIcon },
          { href: "/settings", label: "Settings", icon: SettingsIcon },
        ],
      },
    ],
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
  const [hydrated, setHydrated] = useState(false);
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

  useEffect(() => {
    setHydrated(true);
  }, []);

  function onLogout() {
    setWebAuth(null);
  }

  // The shell owns browser-only auth, theme, and navigation state. Rendering a
  // stable placeholder until hydration prevents those values from invalidating
  // the server markup and, critically, leaves native sidebar links usable.
  if (!hydrated) {
    return (
      <DashboardShell>
        <main className="flex min-h-screen flex-1 items-center justify-center" aria-busy="true" aria-label="Loading workspace" />
      </DashboardShell>
    );
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
          <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
            <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-page-gap">{children}</div>
          </main>
        </div>
      </DashboardShell>
    </DashboardPageContext.Provider>
  );
}

export function DashboardShell({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-background text-foreground lg:flex lg:bg-transparent">{children}</div>;
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
        "flex h-full flex-col rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(8,15,30,0.92),rgba(6,12,24,0.86))] text-foreground shadow-[0_24px_70px_rgba(2,6,23,0.42)] ring-1 ring-inset ring-white/8 backdrop-blur-2xl",
        collapsed ? "w-[5.5rem]" : "w-72",
      )}
    >
      <div className="border-b border-white/10 px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <a href="/overview" className="flex min-w-0 items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-sky-300/20 bg-sky-400/12 text-sky-300 shadow-[0_10px_28px_rgba(56,189,248,0.16)] ring-1 ring-inset ring-white/10">
              <KnightIcon className="h-[1.15rem] w-[1.15rem]" />
            </div>
            {!collapsed ? (
              <div className="min-w-0">
                <p className="truncate text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">Chess</p>
                <p className="truncate text-xl font-semibold text-slate-50">Chess</p>
              </div>
            ) : null}
          </a>
          <button
            type="button"
            onClick={onCollapseToggle}
            className="hidden rounded-xl border border-white/10 bg-white/5 p-2 text-slate-400 transition hover:bg-white/10 hover:text-slate-100 lg:inline-flex"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
            <PanelIcon className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-6">
        <nav className="grid gap-6">
          {navSections.map((section) => (
            <div key={section.label} className="grid gap-3">
              <p className={cn("px-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500/80", collapsed && "px-0 text-center")}>{collapsed ? section.label.slice(0, 1) : section.label}</p>
              <div className="grid gap-3">
                {section.groups.map((group) => (
                  <div key={group.label} className="grid gap-1">
                    {!collapsed ? (
                      <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500/65">
                        {group.label}
                      </p>
                    ) : null}
                    {group.items.map((item) => {
                      const active = item.match ? item.match(pathname) : pathname === item.href;
                      return (
                        <a
                          key={item.href}
                          href={item.href}
                          onClick={onMobileClose}
                          className={cn(
                            "group relative flex items-center gap-3 overflow-hidden rounded-[1.1rem] border border-transparent px-3 py-3 text-sm font-medium text-slate-300/78 transition duration-200 hover:border-white/10 hover:bg-white/6 hover:text-slate-100",
                            collapsed && "justify-center px-2",
                            active && "border-sky-300/20 bg-[linear-gradient(180deg,rgba(59,130,246,0.18),rgba(30,41,59,0.34))] text-slate-50 shadow-[0_14px_30px_rgba(15,23,42,0.22)]",
                          )}
                          aria-current={active ? "page" : undefined}
                        >
                          <span className={cn("absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-sky-300 opacity-0 transition", active && "opacity-100", collapsed && "inset-x-2 inset-y-auto bottom-0 left-2 h-1 w-auto rounded-t-full rounded-r-none")} />
                          <span className={cn("flex h-9 w-9 items-center justify-center rounded-xl border border-transparent bg-transparent text-slate-400 transition group-hover:border-white/10 group-hover:bg-white/10 group-hover:text-sky-300", active && "border-sky-300/15 bg-sky-400/10 text-sky-300")}>
                            {item.icon({ className: "h-4 w-4" })}
                          </span>
                          {!collapsed ? <span className="truncate">{item.label}</span> : null}
                        </a>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </div>
    </div>
  );

  return (
    <>
      <aside className="sticky top-0 hidden h-screen shrink-0 border-r border-white/6 bg-[rgba(2,6,23,0.34)] p-4 backdrop-blur-xl lg:block">{sidebar}</aside>
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
    <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(2,6,23,0.48)] backdrop-blur-2xl">
      <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-4 px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <button
              type="button"
              onClick={onMobileMenuToggle}
              className="inline-flex rounded-2xl border border-border/70 bg-card/90 px-3 py-2 text-muted-foreground shadow-soft transition hover:bg-overlay hover:text-foreground lg:hidden"
              aria-label="Open navigation"
            >
              <MenuIcon className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-50 sm:text-[2.15rem]">{title}</h1>
              {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300/78">{description}</p> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3">
            {actions}
            <HeaderIconButton label="Notifications"><BellIcon className="h-5 w-5" /></HeaderIconButton>
            <HeaderIconButton label="Alerts"><BellDotIcon className="h-5 w-5" /></HeaderIconButton>
            <ThemeToggle />
            <div className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.18),rgba(30,41,59,0.28))] text-sm font-semibold text-slate-50 shadow-[0_12px_24px_rgba(15,23,42,0.28)]">CG</div>
            <a href="/login" onClick={onLogout}>
              <Button variant="ghost" className="border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10">Log out</Button>
            </a>
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
      className="border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      aria-pressed={isDark}
    >
      <span aria-hidden="true" className="flex h-5 w-5 items-center justify-center">{isDark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}</span>
      {isDark ? "Light mode" : "Dark mode"}
    </Button>
  );
}

export function DashboardContentGrid({
  children,
  utility,
  className,
  workspaceClassName,
  utilityClassName,
}: DashboardContentGridProps) {
  return (
    <div
      className={cn(
        "grid gap-page-gap",
        utility ? "xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start" : undefined,
        className,
      )}
    >
      <div className={cn("min-w-0 grid gap-page-gap", workspaceClassName)}>{children}</div>
      {utility ? <aside className={cn("min-w-0 grid gap-page-gap", utilityClassName)}>{utility}</aside> : null}
    </div>
  );
}

export function PageContainer({
  title,
  description,
  actions,
  children,
  rightRail,
  className,
  contentGridClassName,
  workspaceClassName,
  rightRailClassName,
}: DashboardPageConfig & {
  children: ReactNode;
  rightRail?: ReactNode;
  className?: string;
  contentGridClassName?: string;
  workspaceClassName?: string;
  rightRailClassName?: string;
}) {
  const context = useContext(DashboardPageContext);

  useEffect(() => {
    context?.setPage({ title, description, actions });
    return () => context?.setPage({});
  }, [actions, context, description, title]);

  return (
    <div className={cn("grid gap-page-gap", className)}>
      <DashboardContentGrid
        utility={rightRail}
        className={contentGridClassName}
        workspaceClassName={workspaceClassName}
        utilityClassName={rightRailClassName}
      >
        {children}
      </DashboardContentGrid>
    </div>
  );
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
function SunIcon({ className }: { className?: string }) { return <IconWrapper className={className}><circle cx="12" cy="12" r="4" /><path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" /></IconWrapper>; }
function MoonIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M20 14.5A7.5 7.5 0 1 1 9.5 4 6.2 6.2 0 0 0 20 14.5Z" /></IconWrapper>; }
function BellIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M15 17H9" /><path d="M18 16V11a6 6 0 1 0-12 0v5l-2 2h16l-2-2Z" /></IconWrapper>; }
function BellDotIcon({ className }: { className?: string }) { return <IconWrapper className={className}><path d="M15 17H9" /><path d="M18 16V11a6 6 0 1 0-12 0v5l-2 2h11" /><circle cx="19" cy="5" r="3" /></IconWrapper>; }
function HeaderIconButton({ label, children }: { label: string; children: ReactNode }) { return <button type="button" aria-label={label} className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-slate-50">{children}</button>; }
