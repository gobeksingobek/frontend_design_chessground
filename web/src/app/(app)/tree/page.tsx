import { TreeExplorer } from "@/components/tree/tree-explorer";

export default function TreePage() {
  return (
    <div className="stack">
      <h2>Tree</h2>
      <p>Build and browse your opening tree from saved lines and sideline analysis jobs.</p>
      <div className="card">
        <TreeExplorer />
      </div>
    </div>
  );
}
