import { ChessBoard } from "@/components/chess/chess-board";
import { TrainerEndpointsPanel } from "@/components/trainer/trainer-endpoints-panel";
import { TrainerQueue } from "@/components/trainer/trainer-queue";

export default function TrainerPage() {
  return (
    <div className="stack">
      <h2>Trainer</h2>
      <p>Queue positions, record outcomes, and apply priority overrides.</p>
      <div className="board-page-layout">
        <div className="card">
          <ChessBoard size="large" title="Training board" />
        </div>
        <div className="stack">
          <TrainerEndpointsPanel />
          <TrainerQueue />
        </div>
      </div>
    </div>
  );
}
