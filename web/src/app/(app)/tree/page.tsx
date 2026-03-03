import { ChessBoard } from "@/components/chess/chess-board";
import Link from "next/link";

export default function TreePage() {
  return (
    <div className="stack">
      <h2>Tree</h2>
      <p>Build and browse your opening tree from saved lines and sideline analysis jobs.</p>
      <div className="card">
        <ChessBoard title="Tree anchor position" />
        <h3>Coming next</h3>
        <ul>
          <li>Interactive move-tree explorer.</li>
          <li>Coverage and branch depth insights.</li>
          <li>
            Cross-linking with analysis results. Start from the <Link href="/analysis">Analysis Board</Link> to queue
            new sidelines.
          </li>
        </ul>
      </div>
    </div>
  );
}
