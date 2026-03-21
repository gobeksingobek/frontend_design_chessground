import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineTable } from "@/components/sideline-table";
import { SectionHeader } from "@/components/ui/section-header";

export default function SidelinesPage() {
  return (
    <PageContainer title="Sidelines" description="Track async sideline generation jobs and review backend results.">
      <PageSection>
        <SectionHeader title="Sideline jobs" description="Use the shared page heading structure to review async sideline jobs from the FastAPI backend." />
        <SidelineTable />
      </PageSection>
    </PageContainer>
  );
}
