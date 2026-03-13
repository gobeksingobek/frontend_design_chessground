"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";
import { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer";

export function TreeEndpointsPanel() {
  const [posId, setPosId] = useState(1);
  const browse = useQuery({ queryKey: ["line-tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["line-tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const canonical = toCanonicalTreeSnapshot(browse.data, coverage.data);

  return <div className="card"><h3>Tree endpoint explorer</h3><input type="number" value={posId} onChange={(e)=>setPosId(Number(e.target.value)||1)} /><p>Coverage {canonical.coveragePct.toFixed(1)}% ({canonical.repertoireCount}/{canonical.gameCount})</p></div>;
}
