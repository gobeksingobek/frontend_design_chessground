"use client";

import { ReactNode } from "react";

import { TreeExplorer, type TreeExplorerLayout } from "@/components/tree/tree-explorer";
import { TreeEndpointsPanel } from "@/components/tree/tree-endpoints-panel";
import { DetailPane, UtilityPanelStack, WorkspaceSection } from "@/components/ui/page-patterns";
import { CardTitle, MutedText } from "@/components/ui/typography";

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
      <DetailPane
        title="Branch workspace"
        description="The board-first workspace keeps the tree presentation scoped to reading and selecting persisted branch data rather than recomputing analysis inline."
      >
        <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.85fr)] xl:items-start">
          <TreeExplorer layout={layout} />
          <UtilityPanelStack>
            {controls}
            <TreeEndpointsPanel />
            <div className="rounded-2xl border border-border/70 bg-card/70 px-4 py-4 shadow-soft">
              <CardTitle className="text-base">Why this module exists</CardTitle>
              <MutedText className="mt-2 text-sm leading-6">
                It isolates the tree into a presentational module so follow-on pages can adopt the same branch rail and workspace framing with minimal regression risk.
              </MutedText>
            </div>
          </UtilityPanelStack>
        </div>
      </DetailPane>
    </WorkspaceSection>
  );
}
