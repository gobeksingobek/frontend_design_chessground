import { ChessBoard } from "@/components/chess/chess-board";
import Link from "next/link";

export default function TrainerPage() {
  return (
    <div className="stack">
      <h2>Trainer</h2>
      <p>Practice repertoire lines directly in the browser and prioritize weak branches.</p>
      <div className="card">
        <ChessBoard title="Trainer practice board" />
        <h3>Coming next</h3>
        <ul>
          <li>Learn mode and Review mode workflows.</li>
          <li>Progress tracking by line and position.</li>
          <li>
            Priority synchronization with sideline outcomes and your <Link href="/games">Games</Link> history.
          </li>
        </ul>
      </div>
    </div>
  );
}
