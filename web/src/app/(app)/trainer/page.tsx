import { TrainerQueue } from "@/components/trainer/trainer-queue";

export default function TrainerPage() {
  return (
    <div className="stack">
      <h2>Trainer</h2>
      <p>Practice repertoire lines directly in the browser and prioritize weak branches.</p>
      <div className="card">
        <TrainerQueue />
      </div>
    </div>
  );
}
