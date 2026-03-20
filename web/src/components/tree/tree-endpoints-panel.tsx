"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";

export function TreeEndpointsPanel() {
  const [posId, setPosId] = useState(1);
  const browse = useQuery({ queryKey: ["line-tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["line-tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const canonical = toCanonicalTreeSnapshot(browse.data, coverage.data);
  return <Card><h3 className="text-base font-semibold">Tree endpoint explorer</h3><label className="grid max-w-xs gap-2 text-sm text-text-subtle">Position id<Input type="number" value={posId} onChange={(e) => setPosId(Number(e.target.value) || 1)} /></label><p className="text-sm text-text-subtle">Coverage {canonical.coveragePct.toFixed(1)}% ({canonical.repertoireCount}/{canonical.gameCount})</p></Card>;
}
