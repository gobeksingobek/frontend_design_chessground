"use client";

import { ReactNode } from "react";

import { TreeExplorer, type TreeExplorerLayout } from "@/components/tree/tree-explorer";
import { TreeEndpointsPanel } from "@/components/tree/tree-endpoints-panel";
import { WorkspaceSection } from "@/components/ui/page-patterns";

export function RepertoireTreeModule({
  title = "Repertoire tree",
  description = "Browse branch structure, coverage, and follow-on game evidence without changing the underlying tree payload contracts.",
  controls,
  layout = "workspace",
}: {
  title?: string;
  description?: ReactNode;
  controls?: ReactNode;
  layout?: TreeExplorerLayout;
}) {
  return (
    <WorkspaceSection title={title} description={description}>
      <TreeExplorer layout={layout} />
      <div className="grid gap-grid-gap lg:grid-cols-2">
        {controls}
        <TreeEndpointsPanel />
      </div>
    </WorkspaceSection>
  );
}
