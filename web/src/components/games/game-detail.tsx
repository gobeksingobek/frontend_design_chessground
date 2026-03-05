"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { EvalBar } from "@/components/games/eval-bar";
import { MoveQualityBadge } from "@/components/games/move-quality-badge";
import { getGame } from "@/lib/api-client";

export function applyCursorKey(key: string, current: number, max: number): number {
  if (key === "ArrowRight") return Math.min(max, current + 1);
  if (key === "ArrowLeft") return Math.max(0, current - 1);
  if (key === "ArrowUp") return max;
  if (key === "ArrowDown") return 0;
  return current;
}

export function GameDetail({ gameId }: { gameId: number }) {
  const [cursorIndex, setCursorIndex] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => getGame(gameId),
  });

  const moves = useMemo(() => data?.moves ?? [], [data]);

  useEffect(() => {
    if (!moves.length) {
      setCursorIndex(0);
      return;
    }
    setCursorIndex((current) => Math.max(0, Math.min(moves.length, current)));
  }, [moves]);

  const selectedMove = useMemo(() => {
    if (cursorIndex === 0) return null;
    return moves[cursorIndex - 1] ?? null;
  }, [moves, cursorIndex]);

  const selectedPly = selectedMove?.ply ?? null;

  const boardFen = useMemo(() => {
    if (!moves.length) return undefined;
    if (cursorIndex === 0) return undefined;
    return selectedMove?.fen ?? undefined;
  }, [moves.length, cursorIndex, selectedMove]);

  const hasEvalData = selectedMove?.pre_eval_cp !== null || selectedMove?.post_eval_cp !== null;

  const navigateNext = useCallback(() => {
    setCursorIndex((current) => Math.min(moves.length, current + 1));
  }, [moves.length]);

  const navigatePrev = useCallback(() => {
    setCursorIndex((current) => Math.max(0, current - 1));
  }, []);

  const navigateStart = useCallback(() => {
    setCursorIndex(0);
  }, []);

  const navigateEnd = useCallback(() => {
    setCursorIndex(moves.length);
  }, [moves.length]);

  const onKeyNavigate = useCallback(
    (event: KeyboardEvent | ReactKeyboardEvent) => {
      const nextCursor = applyCursorKey(event.key, cursorIndex, moves.length);
      if (nextCursor !== cursorIndex) {
        event.preventDefault();
        setCursorIndex(nextCursor);
      }
    },
    [cursorIndex, moves.length],
  );

  useEffect(() => {
    const handler = (event: KeyboardEvent) => onKeyNavigate(event);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onKeyNavigate]);

  if (isLoading) return <p>Loading game detail...</p>;
  if (error) return <p>Failed to load game detail: {(error as Error).message}</p>;

  return (
    <div className="stack" onKeyDown={onKeyNavigate} tabIndex={0}>
      <div className="card">
        <h3>Header</h3>
        <pre className="code">{JSON.stringify(data?.header, null, 2)}</pre>
      </div>

      <div className="card">
        <h3>Create sideline analysis job</h3>
        <ChessBoard
          fen={boardFen}
          title="Selected game position"
          currentPlyIndex={cursorIndex}
          onNavigateNext={navigateNext}
          onNavigatePrev={navigatePrev}
          onNavigateStart={navigateStart}
          onNavigateEnd={navigateEnd}
          onMoveAttempt={({ uci }) => {
            const nextMove = moves[cursorIndex];
            if (nextMove?.uci_move === uci) {
              navigateNext();
            }
          }}
        />
        <label>
          Move ply
          <select
            value={selectedPly ?? ""}
            onChange={(event) => {
              const ply = event.target.value ? Number(event.target.value) : null;
              if (ply === null) {
                setCursorIndex(0);
                return;
              }
              const moveIndex = moves.findIndex((move) => move.ply === ply);
              setCursorIndex(moveIndex >= 0 ? moveIndex + 1 : 0);
            }}
          >
            <option value="">Initial position</option>
            {moves.map((move) => (
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
            {moves.map((move) => (
              <tr
                key={move.ply}
                className={move.ply === selectedPly ? "move-row-selected" : "move-row"}
                onClick={() => {
                  const moveIndex = moves.findIndex((candidate) => candidate.ply === move.ply);
                  setCursorIndex(moveIndex + 1);
                }}
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
