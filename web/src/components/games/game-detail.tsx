"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { EvalBar } from "@/components/games/eval-bar";
import { MoveQualityBadge } from "@/components/games/move-quality-badge";
import { getGame } from "@/lib/api-client";

export function GameDetail({ gameId }: { gameId: number }) {
  const [selectedPly, setSelectedPly] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => getGame(gameId),
  });

  const selectedMove = useMemo(() => {
    if (!data || selectedPly === null) return null;
    return data.moves.find((move) => move.ply === selectedPly) ?? null;
  }, [data, selectedPly]);

  const hasEvalData = selectedMove?.pre_eval_cp !== null || selectedMove?.post_eval_cp !== null;

  if (isLoading) return <p>Loading game detail...</p>;
  if (error) return <p>Failed to load game detail: {(error as Error).message}</p>;

  return (
    <div className="stack">
      <div className="card">
        <h3>Header</h3>
        <pre className="code">{JSON.stringify(data?.header, null, 2)}</pre>
      </div>

      <div className="card">
        <h3>Create sideline analysis job</h3>
        <ChessBoard fen={selectedMove?.fen ?? undefined} title="Selected game position" />
        <label>
          Move ply
          <select
            value={selectedPly ?? ""}
            onChange={(event) => setSelectedPly(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">Select a move...</option>
            {data?.moves.map((move) => (
              <option key={move.ply} value={move.ply}>
                Ply {move.ply} - {move.san_move ?? move.uci_move ?? "-"}
              </option>
            ))}
          </select>
        </label>

        {selectedMove?.fen ? (
          <p>
            <Link
              href={{
                pathname: "/analysis",
                query: { game_id: String(gameId), move_ply: String(selectedMove.ply), fen: selectedMove.fen },
              }}
            >
              Open in /analysis with this position
            </Link>
          </p>
        ) : null}

        {selectedMove?.fen ? (
          <SidelineAnalysisForm
            key={`${selectedMove.ply}-${selectedMove.fen}`}
            title="Queue sideline from this game move"
            initialGameId={String(gameId)}
            initialMovePly={selectedMove.ply}
            initialFen={selectedMove.fen}
            lockedFields={{ gameId: true, movePly: true, fen: true }}
          />
        ) : (
          <small>Select a move with available FEN to run quick eval.</small>
        )}

        {selectedMove ? (
          <div className="eval-grid">
            <div className="card eval-trend-card">
              <h4>Selected ply details</h4>
              <p>
                Ply {selectedMove.ply}: {selectedMove.san_move ?? selectedMove.uci_move ?? "-"}
              </p>
              <p>
                Quality: <MoveQualityBadge label={selectedMove.quality_label} />
              </p>
              <p className={selectedMove.your_cpl !== null && selectedMove.your_cpl > 120 ? "cpl-high" : "cpl-low"}>
                Your CPL: {selectedMove.your_cpl ?? "-"}
              </p>
            </div>

            {hasEvalData ? (
              <>
                <EvalBar evalCp={selectedMove.pre_eval_cp} title="Before move" />
                <EvalBar evalCp={selectedMove.post_eval_cp} title="After move" />
              </>
            ) : (
              <div className="card">
                <h4>Eval panel</h4>
                <small>No pre/post eval values are available for the selected move.</small>
              </div>
            )}
          </div>
        ) : null}
      </div>

      <div className="card">
        <h3>Moves</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Ply</th>
              <th>SAN</th>
              <th>UCI</th>
              <th>Class</th>
              <th>Quality</th>
              <th>Your CPL</th>
            </tr>
          </thead>
          <tbody>
            {data?.moves.map((move) => (
              <tr
                key={move.ply}
                className={move.ply === selectedMove?.ply ? "move-row-selected" : "move-row"}
                onClick={() => setSelectedPly(move.ply)}
              >
                <td>{move.ply}</td>
                <td>{move.san_move ?? "-"}</td>
                <td>{move.uci_move ?? "-"}</td>
                <td>{move.repertoire_class ?? "-"}</td>
                <td>
                  <MoveQualityBadge label={move.quality_label} />
                </td>
                <td className={move.your_cpl !== null && move.your_cpl > 120 ? "cpl-high" : "cpl-low"}>{move.your_cpl ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
