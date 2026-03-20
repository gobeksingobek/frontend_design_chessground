import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineTable } from "@/components/sideline-table";
import { SectionHeader } from "@/components/ui/section-header";

export default function SidelinesPage() {
  return <PageContainer title="Sidelines" description="Track async sideline generation jobs and review backend results."><PageSection><SectionHeader title="Sidelines" description="Async sideline jobs from the FastAPI backend." /><SidelineTable /></PageSection></PageContainer>;
}
