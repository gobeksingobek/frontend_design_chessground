"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { RepertoireTree } from "@/components/tree/repertoire-tree";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MutedText } from "@/components/ui/typography";
import { getLineTreeBranchMetrics, getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";

export interface CanonicalTreeSnapshot { posId: number; coveragePct: number; repertoireCount: number; gameCount: number; }
export function toCanonicalTreeSnapshot(browse: any, coverage: any): CanonicalTreeSnapshot { return { posId: Number(browse?.pos_id ?? coverage?.pos_id ?? 1), coveragePct: Number(coverage?.coverage_pct ?? 0), repertoireCount: Number(browse?.repertoire_children?.length ?? 0), gameCount: Number(browse?.game_children?.length ?? 0) }; }

export function TreeExplorer() {
  const [posId, setPosId] = useState(1);
  const [selectedMoveUci, setSelectedMoveUci] = useState<string | null>(null);
  const browse = useQuery({ queryKey: ["tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const metrics = useQuery({ queryKey: ["tree", "metrics", posId], queryFn: () => getLineTreeBranchMetrics(posId, true) });
  const canonical = toCanonicalTreeSnapshot(browse.data, coverage.data);

  const defaultSelectedMove = useMemo(() => browse.data?.repertoire_children.find((move) => move.is_user_mainline)?.uci_move ?? browse.data?.repertoire_children[0]?.uci_move ?? null, [browse.data]);
  const resolvedSelectedMove = selectedMoveUci ?? defaultSelectedMove;

  return (
    <div className="grid gap-4">
      <Card className="gap-3">
        <label className="grid max-w-xs gap-2 text-sm text-text-subtle">
          Position id
          <Input type="number" value={posId} onChange={(e) => { setPosId(Number(e.target.value) || 1); setSelectedMoveUci(null); }} />
        </label>
        <p className="text-sm text-text-subtle">Coverage {canonical.coveragePct.toFixed(1)}% · rep {canonical.repertoireCount} · games {canonical.gameCount} · top {metrics.data?.top_game_branches.length ?? 0}</p>
        <MutedText className="text-sm">This preview keeps the data contract unchanged and focuses on the under-board presentation for branch scanning.</MutedText>
      </Card>

      {browse.data ? (
        <RepertoireTree
          browse={browse.data}
          coverage={coverage.data}
          metrics={metrics.data}
          selectedMoveUci={resolvedSelectedMove}
          onSelectMove={setSelectedMoveUci}
        />
      ) : (
        <Card variant="soft">
          <MutedText>Loading tree presentation...</MutedText>
        </Card>
      )}
    </div>
  );
}
