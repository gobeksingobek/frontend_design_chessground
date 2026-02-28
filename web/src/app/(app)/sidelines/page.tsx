import { SidelineTable } from "@/components/sideline-table";

export default function SidelinesPage() {
  return (
    <div className="stack">
      <h2>Sidelines</h2>
      <p>Async sideline jobs from FastAPI backend.</p>
      <SidelineTable />
    </div>
  );
}
