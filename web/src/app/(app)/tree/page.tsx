import { PageContainer, PageSection } from "@/components/app-shell";
import { TreeExplorer } from "@/components/tree/tree-explorer";
import { TreeEndpointsPanel } from "@/components/tree/tree-endpoints-panel";
import { SectionHeader } from "@/components/ui/section-header";

export default function TreePage() {
  return <PageContainer title="Tree Explorer" description="Browse tree endpoints for branch navigation, coverage, and move metrics."><PageSection><SectionHeader title="Tree" description="Browse line-tree endpoints for branch navigation, coverage, and branch metrics." /><TreeEndpointsPanel /><TreeExplorer /></PageSection></PageContainer>;
}
