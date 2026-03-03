import { TrainerEndpointsPanel } from "@/components/trainer/trainer-endpoints-panel";
import { TrainerQueue } from "@/components/trainer/trainer-queue";

export default function TrainerPage() {
  return (
    <div className="stack">
      <h2>Trainer</h2>
      <p>Queue positions, record outcomes, and apply priority overrides.</p>
      <TrainerEndpointsPanel />
      <TrainerQueue />
    </div>
  );
}
