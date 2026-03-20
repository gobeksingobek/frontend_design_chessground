import { SidelineTable } from "@/components/sideline-table";
import { SectionHeader } from "@/components/ui/section-header";

export default function SidelinesPage() {
  return <div className="grid gap-4"><SectionHeader title="Sidelines" description="Async sideline jobs from the FastAPI backend." /><SidelineTable /></div>;
}
