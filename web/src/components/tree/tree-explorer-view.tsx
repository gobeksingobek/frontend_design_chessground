"use client";

import { type ReactNode, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { BodyText, CaptionText, CardTitle, MutedText } from "@/components/ui/typography";
import type { PositionIntelligenceResponse, TreeBranchMetricsResponse, TreeBrowseMove, TreeBrowseResponse, TreeCoverageResponse, TreeGameMove } from "@/lib/types";
import { cn } from "@/lib/cn";
import { toCanonicalTreeSnapshot, toNavigablePositionId, toPositionIntelligencePanelState } from "./tree-explorer-shared";

export type TreeExplorerLayout = "workspace" | "utility" | "stacked";

type RepertoireTab = "white" | "black" | "favorites";

type BranchRow = {
  key: string;
  move: string;
  detail: string;
  meta: string;
  nextPosId?: number | null;
  emphasis?: boolean;
  icon: "repertoire" | "games" | "favorite";
};

const tabs: Array<{ id: RepertoireTab; label: string; icon: (className?: string) => ReactNode }> = [
  { id: "white", label: "White", icon: (className) => <ArrowCornerIcon className={className} /> },
  { id: "black", label: "Black", icon: (className) => <ChessTowerIcon className={className} /> },
  { id: "favorites", label: "Favorites", icon: (className) => <StarIcon className={className} /> },
];

function toRepertoireRows(moves: TreeBrowseMove[]): BranchRow[] {
  return moves.map((move, index) => ({
    key: `rep-${move.uci_move}`,
    move: move.san_move ?? move.uci_move,
    detail: move.is_user_mainline ? "Main repertoire path" : move.is_priority_edge ? "Priority branch" : "Tracked response",
    meta: move.uci_move,
    nextPosId: move.next_pos_id,
    emphasis: Boolean(index === 0 || move.is_user_mainline),
    icon: "repertoire",
  }));
}

function toGameRows(moves: TreeGameMove[]): BranchRow[] {
  return moves.map((move, index) => ({
    key: `game-${move.uci_move}`,
    move: move.san_move ?? move.uci_move,
    detail: `${move.games} games · ${Math.round(move.score_pct)}% score · ${move.avg_opp_elo ? `avg ${Math.round(move.avg_opp_elo)}` : "observed line"}`,
    meta: move.uci_move,
    nextPosId: move.next_pos_id,
    emphasis: index === 0,
    icon: index < 2 ? "favorite" : "games",
  }));
}

export function TreeExplorerView({
  posId,
  onPosIdChange,
  browse,
  coverage,
  metrics,
  intelligence,
  selectedMoveUci,
  onSelectMove,
  isLoading,
  isError,
  errorMessage,
}: {
  posId: number;
  onPosIdChange: (value: number) => void;
  browse?: TreeBrowseResponse;
  coverage?: TreeCoverageResponse;
  metrics?: TreeBranchMetricsResponse;
  intelligence?: PositionIntelligenceResponse;
  selectedMoveUci?: string | null;
  onSelectMove?: (uciMove: string | null) => void;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  layout?: TreeExplorerLayout;
}) {
  const [activeTab, setActiveTab] = useState<RepertoireTab>("white");
  const canonical = toCanonicalTreeSnapshot(browse, coverage);

  const whiteRows = useMemo(() => (browse ? toRepertoireRows(browse.repertoire_children) : []), [browse]);
  const blackRows = useMemo(() => {
    const source = metrics?.top_game_branches?.length ? metrics.top_game_branches : browse?.game_children ?? [];
    return toGameRows(source);
  }, [browse, metrics]);
  const favoriteRows = useMemo(() => [...whiteRows.filter((row) => row.emphasis), ...blackRows.filter((row) => row.icon === "favorite")].slice(0, 6), [blackRows, whiteRows]);

  const activeRows = activeTab === "white" ? whiteRows : activeTab === "black" ? blackRows : favoriteRows;
  const moveList = [selectedMoveUci, ...activeRows.map((row) => row.meta)].filter(Boolean).slice(0, 5).join(" · ");
  const whiteProgress = canonical.repertoireCount > 0 ? Math.min(100, Math.round(canonical.coveragePct || 0)) : 0;
  const blackProgress = canonical.gameCount > 0 ? Math.min(100, Math.round((canonical.gameCount / Math.max(canonical.gameCount + canonical.repertoireCount, 1)) * 100)) : 0;

  if (isLoading) {
    return (
      <div className="grid gap-6">
        <Skeleton className="h-14 w-80 rounded-2xl" />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_22rem]">
          <Skeleton className="h-[32rem] rounded-[2rem]" />
          <Skeleton className="h-[32rem] rounded-[2rem]" />
          <div className="grid gap-6">
            <Skeleton className="h-44 rounded-[2rem]" />
            <Skeleton className="h-56 rounded-[2rem]" />
            <Skeleton className="h-44 rounded-[2rem]" />
          </div>
        </div>
        <Skeleton className="h-64 rounded-[2rem]" />
      </div>
    );
  }

  if (isError) {
    return <EmptyState title="Unable to load repertoire workspace" description={errorMessage ?? "The current tree endpoints did not return a usable response for this position."} />;
  }

  if (!browse) {
    return <EmptyState title="No repertoire workspace data" description="Load a valid position to render the repertoire dashboard." />;
  }

  return (
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top,rgba(148,163,184,0.18),transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.86),rgba(2,6,23,0.94))] p-5 shadow-[0_28px_80px_rgba(2,6,23,0.45)] ring-1 ring-inset ring-white/10 backdrop-blur-2xl md:p-7">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(96,165,250,0.14),transparent_24%),radial-gradient(circle_at_85%_15%,rgba(255,255,255,0.08),transparent_18%),radial-gradient(circle_at_55%_75%,rgba(148,163,184,0.08),transparent_26%)] opacity-90" />
      <div className="relative grid gap-6">
        <div className="flex flex-col gap-4 border-b border-white/10 pb-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="grid gap-4">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-50 sm:text-[2.6rem]">Opening Repertoire</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300/80">
                A dark glass workspace tuned to keep the tab rail, repertoire trees, and quick tools aligned exactly where users expect them.
              </p>
            </div>
            <div className="inline-flex w-fit flex-wrap items-center gap-1 rounded-2xl border border-white/10 bg-white/5 p-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl">
              {tabs.map((tab) => {
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "inline-flex min-w-[9rem] items-center justify-center gap-2 rounded-[1rem] px-4 py-3 text-base font-semibold transition",
                      active
                        ? "bg-[linear-gradient(180deg,rgba(148,163,184,0.28),rgba(59,130,246,0.18))] text-slate-50 shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_12px_24px_rgba(37,99,235,0.18)] ring-1 ring-inset ring-sky-300/35"
                        : "text-slate-300/78 hover:bg-white/6 hover:text-slate-100",
                    )}
                  >
                    {tab.icon("h-4 w-4")}
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[24rem]">
            <GlassMetric label="Position" value={`#${browse.pos_id}`} detail="Current root" />
            <label className="grid gap-2 rounded-[1.5rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-300/80 backdrop-blur-xl">
              Position id
              <Input type="number" value={posId} onChange={(event) => onPosIdChange(Number(event.target.value) || 1)} className="border-white/10 bg-white/5 text-slate-100" />
            </label>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_22rem] xl:items-start">
          <BranchPanel
            title="White Repertoire"
            subtitle={whiteRows[0]?.move ?? "No white branches yet"}
            rows={whiteRows}
            selectedMoveUci={selectedMoveUci}
            onSelectMove={onSelectMove}
            onOpenPosition={onPosIdChange}
          />
          <BranchPanel
            title="Black Repertoire"
            subtitle={blackRows[0]?.move ?? "No black branches yet"}
            rows={activeTab === "favorites" ? favoriteRows : blackRows}
            selectedMoveUci={selectedMoveUci}
            onSelectMove={onSelectMove}
            onOpenPosition={onPosIdChange}
          />
          <div className="grid gap-5">
            <InfoCard title="Info & Tools">
              <div className="grid gap-4">
                <InfoLabel label="Move List" value={moveList || "No moves selected"} />
                <div className="grid gap-3 text-sm text-slate-300/85">
                  <p>Coverage reads directly from persisted tree payloads.</p>
                  <p>Selections stay aligned with the current tab and branch rails.</p>
                </div>
              </div>
            </InfoCard>
            <PositionIntelligenceCard intelligence={intelligence} />
            <InfoCard title="Tips">
              <ul className="grid gap-3 pl-5 text-sm leading-6 text-slate-300/85 marker:text-sky-300">
                <li>Focus on the first high-priority continuations.</li>
                <li>Use Favorites for your recurring repertoire checkpoints.</li>
                <li>Keep the position control nearby for fast branch jumping.</li>
              </ul>
            </InfoCard>
            <InfoCard title="Debug Info">
              <div className="grid gap-2 text-sm text-slate-300/85">
                <div className="flex items-center justify-between gap-4"><span>Path</span><span className="font-medium text-slate-100">/tree</span></div>
                <div className="flex items-center justify-between gap-4"><span>Status</span><span className="font-medium text-emerald-300">Active</span></div>
                <div className="flex items-center justify-between gap-4"><span>Coverage</span><span className="font-medium text-slate-100">{canonical.coveragePct.toFixed(1)}%</span></div>
                <div className="flex items-center justify-between gap-4"><span>Games</span><span className="font-medium text-slate-100">{canonical.gameCount}</span></div>
              </div>
            </InfoCard>
          </div>
        </div>

        <InfoCard title="Training Progress" className="gap-6">
          <ProgressRow label="White Lines Learned" value={whiteProgress} tone="emerald" />
          <ProgressRow label="Black Lines Learned" value={blackProgress} tone="sky" />
          <div className="grid gap-3 sm:grid-cols-3">
            <GlassMetric label="Repertoire" value={String(canonical.repertoireCount)} detail="Tracked branches" />
            <GlassMetric label="Games" value={String(canonical.gameCount)} detail="Observed continuations" />
            <GlassMetric label="Top branches" value={String(metrics?.top_game_branches.length ?? 0)} detail="From metrics payload" />
          </div>
        </InfoCard>
      </div>
    </div>
  );
}

function BranchPanel({
  title,
  subtitle,
  rows,
  selectedMoveUci,
  onSelectMove,
  onOpenPosition,
}: {
  title: string;
  subtitle: string;
  rows: BranchRow[];
  selectedMoveUci?: string | null;
  onSelectMove?: (uciMove: string | null) => void;
  onOpenPosition?: (posId: number) => void;
}) {
  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(15,23,42,0.22))] px-5 py-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-2xl md:px-6 md:py-6">
      <div className="border-b border-white/10 pb-5">
        <CardTitle className="text-[2rem] font-semibold tracking-tight text-slate-50">{title}</CardTitle>
        <BodyText className="mt-3 text-[1.8rem] font-semibold text-white/90">{subtitle}</BodyText>
      </div>
      <div className="mt-5 grid gap-4">
        {rows.length > 0 ? (
          rows.map((row, index) => {
            const selected = selectedMoveUci ? row.meta === selectedMoveUci : index === 0;
            const nextPosId = toNavigablePositionId(row.nextPosId);
            return (
              <div key={row.key} className="relative pl-14">
                <span className={cn("absolute left-6 top-0 w-px bg-slate-500/45", index === rows.length - 1 ? "h-8" : "h-[calc(100%+1rem)]")} />
                <span className="absolute left-6 top-8 h-px w-8 bg-slate-500/45" />
                <span className={cn("absolute left-[18px] top-[26px] h-4 w-4 rounded-full border", selected ? "border-sky-300 bg-sky-300 shadow-[0_0_0_6px_rgba(56,189,248,0.14)]" : "border-slate-400/45 bg-slate-800/90")} />
                <button
                  type="button"
                  onClick={() => onSelectMove?.(row.meta)}
                  className={cn(
                    "grid w-full gap-2 rounded-[1rem] border px-4 py-3 text-left transition backdrop-blur-xl",
                    selected
                      ? "border-sky-300/30 bg-[linear-gradient(180deg,rgba(59,130,246,0.18),rgba(30,41,59,0.42))] text-slate-50 shadow-[0_16px_30px_rgba(15,23,42,0.22)]"
                      : "border-white/8 bg-white/6 text-slate-100 hover:bg-white/10",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-slate-100">
                      {row.icon === "repertoire" ? <ArrowCornerIcon className="h-4 w-4" /> : row.icon === "favorite" ? <StarIcon className="h-4 w-4" /> : <ChessTowerIcon className="h-4 w-4" />}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-lg font-semibold">{row.move}</p>
                      <p className="truncate text-sm text-slate-300/72">{row.detail}</p>
                    </div>
                  </div>
                  <p className="text-sm font-medium text-slate-300/80">{row.meta}</p>
                </button>
                {nextPosId ? (
                  <button
                    type="button"
                    onClick={() => onOpenPosition?.(nextPosId)}
                    className="mt-2 text-sm font-medium text-sky-200 transition hover:text-sky-100"
                  >
                    Open position #{nextPosId}
                  </button>
                ) : null}
              </div>
            );
          })
        ) : (
          <MutedText className="text-sm text-slate-400">No branches available for this column yet.</MutedText>
        )}
      </div>
    </section>
  );
}

function InfoCard({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn("grid gap-4 rounded-[1.6rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(2,6,23,0.26))] px-5 py-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-2xl", className)}>
      <div className="border-b border-white/10 pb-3">
        <CardTitle className="text-xl font-semibold text-slate-50">{title}</CardTitle>
      </div>
      {children}
    </section>
  );
}

function PositionIntelligenceCard({ intelligence }: { intelligence?: PositionIntelligenceResponse }) {
  const panel = toPositionIntelligencePanelState(intelligence);

  return (
    <InfoCard title="Position Intelligence">
      {intelligence ? (
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-3">
            <GlassMetric label="Coverage" value={`${Math.round(intelligence.coverage.coverage_pct)}%`} detail={`${intelligence.coverage.covered_by_games}/${intelligence.coverage.total_repertoire_moves} rep moves`} />
            <GlassMetric label="Games" value={String(intelligence.outcome_summary.games)} detail={`${intelligence.outcome_summary.wins}-${intelligence.outcome_summary.draws}-${intelligence.outcome_summary.losses} · ${Math.round(intelligence.outcome_summary.score_pct)}% score`} />
            <GlassMetric label="Deviations" value={String(intelligence.coverage.played_non_repertoire_moves)} detail={`${intelligence.coverage.opponent_deviation_count} opp exits`} />
            <GlassMetric label="Avg exit eval" value={intelligence.evaluation_summary.avg_exit_eval_cp === null ? "-" : String(Math.round(intelligence.evaluation_summary.avg_exit_eval_cp))} detail={intelligence.evaluation_summary.best_uci ? `Best ${intelligence.evaluation_summary.best_uci}` : "Persisted evals"} />
            <GlassMetric label="Avg CPL" value={intelligence.evaluation_summary.avg_your_cpl === null ? "-" : String(Math.round(intelligence.evaluation_summary.avg_your_cpl))} detail={intelligence.evaluation_summary.avg_rep_cpl === null ? "No repertoire baseline" : `Rep CPL ${Math.round(intelligence.evaluation_summary.avg_rep_cpl)}`} />
          </div>

          <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-300/85">
            Position #{intelligence.position.pos_id} · {intelligence.position.side_to_move === "w" ? "White" : intelligence.position.side_to_move === "b" ? "Black" : "Unknown"} to move
          </div>

          <MiniMoveList title="Repertoire expects" moves={panel.topRepertoireMoves} empty="No repertoire continuations." />
          <MiniMoveList title="Games actually play" moves={panel.topGameMoves} empty="No game continuations." />

          {panel.matters.length > 0 ? (
            <div className="grid gap-2">
              <CaptionText>Why this position matters</CaptionText>
              <ul className="grid gap-2 pl-4 text-sm leading-5 text-slate-300/85 marker:text-sky-300">
                {panel.matters.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            </div>
          ) : (
            <MutedText className="text-sm">Low-signal position: no game, deviation, or CPL evidence is persisted yet.</MutedText>
          )}

          {panel.recentGameLabels.length > 0 ? (
            <div className="grid gap-2">
              <CaptionText>Recent evidence</CaptionText>
              <div className="grid gap-2">
                {panel.recentGameLabels.map((label) => (
                  <div key={label} className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-300/85">
                    {label}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <MutedText className="text-sm">Loading persisted position evidence...</MutedText>
      )}
    </InfoCard>
  );
}

function MiniMoveList({ title, moves, empty }: { title: string; moves: string[]; empty: string }) {
  return (
    <div className="grid gap-2">
      <CaptionText>{title}</CaptionText>
      {moves.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {moves.map((move) => <span key={move} className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-sm font-medium text-slate-100">{move}</span>)}
        </div>
      ) : (
        <MutedText className="text-sm">{empty}</MutedText>
      )}
    </div>
  );
}

function InfoLabel({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2">
      <p className="text-sm font-medium text-slate-300/78">{label}</p>
      <div className="rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-base font-medium text-slate-100">{value}</div>
    </div>
  );
}

function ProgressRow({ label, value, tone }: { label: string; value: number; tone: "emerald" | "sky" }) {
  const fillClass = tone === "emerald"
    ? "from-emerald-400 via-teal-400 to-emerald-300"
    : "from-sky-500 via-blue-500 to-indigo-400";

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-4">
        <p className="text-lg font-medium text-slate-100">{label}</p>
        <div className="rounded-[1rem] border border-white/10 bg-black/20 px-4 py-2 text-2xl font-semibold text-slate-50">{value}%</div>
      </div>
      <div className="h-4 overflow-hidden rounded-full bg-white/10 ring-1 ring-inset ring-white/10">
        <div className={cn("h-full rounded-full bg-gradient-to-r", fillClass)} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function GlassMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-[1.25rem] border border-white/10 bg-white/5 px-4 py-4 text-slate-100 backdrop-blur-xl">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-50">{value}</p>
      <p className="mt-1 text-sm text-slate-300/72">{detail}</p>
    </div>
  );
}

function IconBase({ className, children }: { className?: string; children: ReactNode }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" className={className}>{children}</svg>;
}

function ArrowCornerIcon({ className }: { className?: string }) {
  return <IconBase className={className}><path d="M7 17 17 7" /><path d="M9 7h8v8" /></IconBase>;
}

function ChessTowerIcon({ className }: { className?: string }) {
  return <IconBase className={className}><path d="M7 20h10" /><path d="M8 20V9h8v11" /><path d="M8 9 9.5 5h5L16 9" /><path d="M9 12h6" /></IconBase>;
}

function StarIcon({ className }: { className?: string }) {
  return <IconBase className={className}><path d="m12 3 2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.8 6.7 19l1-5.8L3.5 9.2l5.9-.9L12 3Z" /></IconBase>;
}
