import { PageContainer, PageSection } from "@/components/app-shell";
import { RepertoireTreeModule } from "@/components/tree/repertoire-tree-module";
import { UtilityPanel } from "@/components/ui/page-patterns";

export default function TreePage() {
  return (
    <PageContainer title="Tree Explorer" description="Browse tree endpoints for branch navigation, coverage, and move metrics.">
      <PageSection>
        <RepertoireTreeModule
          controls={(
            <UtilityPanel
              eyebrow="Product priority"
              title="Why tree is the next page"
              description="Tree exploration benefits most from the same board-first workspace pattern because users compare branch context, coverage, and follow-on moves in one reading flow."
            >
              <div className="grid gap-2 text-sm text-muted-foreground">
                <p>The redesign stays scoped to branch-heavy pages instead of rewriting unrelated tables for visual consistency alone.</p>
                <p>Lines and repertoire import remain unchanged because they do not depend on the same board-dominant workspace.</p>
              </div>
            </UtilityPanel>
          )}
        />
      </PageSection>
    </PageContainer>
  );
}
