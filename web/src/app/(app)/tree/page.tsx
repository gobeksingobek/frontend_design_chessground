import { Suspense } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { RepertoireTreeModule } from "@/components/tree/repertoire-tree-module";
import { UtilityPanel } from "@/components/ui/page-patterns";

export default function TreePage() {
  return (
    <PageContainer title="Tree Explorer" description="Browse tree endpoints for branch navigation, coverage, and move metrics.">
      <PageSection>
        <Suspense fallback={<div className="min-h-64" aria-busy="true" aria-label="Loading tree explorer" />}>
          <RepertoireTreeModule
            controls={(
              <UtilityPanel
                eyebrow="Navigation"
                title="Explore persisted branches"
                description="Select a continuation, open its saved position, and compare repertoire coverage with observed game play."
              >
                <div className="grid gap-2 text-sm text-muted-foreground">
                  <p>White, black, and favorite tabs keep branch selection focused without changing the underlying position.</p>
                  <p>Position intelligence remains sourced from the backend&apos;s persisted analysis data.</p>
                </div>
              </UtilityPanel>
            )}
          />
        </Suspense>
      </PageSection>
    </PageContainer>
  );
}
