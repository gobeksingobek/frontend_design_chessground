import { TreeExplorer } from "@/components/tree/tree-explorer";
import { TreeEndpointsPanel } from "@/components/tree/tree-endpoints-panel";

export default function TreePage() {
  return (
    <div className="stack">
      <h2>Tree</h2>
      <p>Browse line-tree endpoints for branch navigation, coverage, and branch metrics.</p>
      <TreeEndpointsPanel />
      <TreeExplorer />
    </div>
  );
}
