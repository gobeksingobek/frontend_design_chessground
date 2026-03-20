import { TreeExplorer } from "@/components/tree/tree-explorer";
import { TreeEndpointsPanel } from "@/components/tree/tree-endpoints-panel";
import { SectionHeader } from "@/components/ui/section-header";

export default function TreePage() {
  return <div className="grid gap-4"><SectionHeader title="Tree" description="Browse line-tree endpoints for branch navigation, coverage, and branch metrics." /><TreeEndpointsPanel /><TreeExplorer /></div>;
}
