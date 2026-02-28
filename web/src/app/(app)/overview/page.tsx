import { SidelineTable } from "@/components/sideline-table";

export default function OverviewPage() {
  return (
    <div className="stack">
      <h2>Overview</h2>
      <p>Phase 1 web shell is active. Backend connectivity is wired through typed API client + React Query.</p>
      <SidelineTable />
    </div>
  );
}
