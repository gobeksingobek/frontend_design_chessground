"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { toCanonicalTreeContract, toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";
import { UtilityPanel } from "@/components/ui/page-patterns";
import { Input } from "@/components/ui/input";
import { BodyText, MutedText } from "@/components/ui/typography";
import { getLineTreeBranchMetrics, getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";

export function TreeEndpointsPanel() {
  const [posId, setPosId] = useState(1);
  const browse = useQuery({ queryKey: ["line-tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["line-tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const metrics = useQuery({ queryKey: ["line-tree", "branch-metrics", posId], queryFn: () => getLineTreeBranchMetrics(posId, true) });
  const canonicalContract = toCanonicalTreeContract({ browse: browse.data, coverage: coverage.data, metrics: metrics.data });
  const canonical = toCanonicalTreeSnapshot(canonicalContract.browse, canonicalContract.coverage, canonicalContract.metrics);
  const idsAgree = [canonicalContract.browse.pos_id, canonicalContract.coverage.pos_id, canonicalContract.metrics.pos_id].every((value) => value === canonical.posId);

  return (
    <UtilityPanel
      eyebrow="Endpoint probe"
      title="Tree endpoint explorer"
      description="Use the canonical /lines/tree/* contract adapter for browse, coverage, and branch metrics endpoint probes."
    >
      <label className="grid gap-2 text-sm text-muted-foreground">
        Position id
        <Input type="number" value={posId} onChange={(e) => setPosId(Number(e.target.value) || 1)} />
      </label>
      <div className="grid gap-1 rounded-xl border border-border/60 bg-background/60 px-3 py-3">
        <BodyText className="text-sm">Coverage {canonical.coveragePct.toFixed(1)}%</BodyText>
        <MutedText className="text-sm">Repertoire {canonical.repertoireCount} · Games {canonical.gameCount}</MutedText>
        <MutedText className="text-sm">Schema ids {idsAgree ? "aligned" : "mismatch"}</MutedText>
      </div>
    </UtilityPanel>
  );
}
