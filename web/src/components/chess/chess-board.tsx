"use client";

import { CSSProperties, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

const FILES = "abcdefgh";
const DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const PIECE_BASE_URL = "https://images.chesscomfiles.com/chess-themes/pieces/neo/150";

interface ChessBoardProps {
  fen?: string;
  title?: string;
  currentPlyIndex?: number;
  onMoveAttempt?: (move: { uci: string; from: string; to: string }) => void;
  onNavigateNext?: () => void;
  onNavigatePrev?: () => void;
  onNavigateStart?: () => void;
  onNavigateEnd?: () => void;
  size?: "default" | "large";
}

function toSquare(rankIndex: number, fileIndex: number): string {
  return `${FILES[fileIndex] ?? "a"}${8 - rankIndex}`;
}

function fenToBoard(fen: string): string[][] {
  const boardPart = fen.trim().split(/\s+/)[0] ?? "";
  const rows = boardPart.split("/");

  if (rows.length !== 8) return fenToBoard(DEFAULT_FEN);

  return rows.map((row) => {
    const squares: string[] = [];
    for (const char of row) {
      const emptyCount = Number(char);
      if (Number.isInteger(emptyCount) && emptyCount > 0) {
        for (let i = 0; i < emptyCount; i += 1) squares.push("");
      } else {
        squares.push(char);
      }
    }
    return squares.length === 8 ? squares : Array.from({ length: 8 }, () => "");
  });
}

function pieceToImageCode(piece: string): string | null {
  if (!piece) return null;
  const side = piece === piece.toUpperCase() ? "w" : "b";
  const kind = piece.toLowerCase();
  return `${side}${kind}`;
}

export function buildMoveAttempt(from: string, to: string): { uci: string; from: string; to: string } {
  return { uci: `${from}${to}`, from, to };
}

function isSameSide(pieceA: string, pieceB: string): boolean {
  if (!pieceA || !pieceB) return false;
  return (pieceA === pieceA.toUpperCase()) === (pieceB === pieceB.toUpperCase());
}

export function ChessBoard({
  fen,
  title,
  currentPlyIndex,
  onMoveAttempt,
  onNavigateNext,
  onNavigatePrev,
  onNavigateStart,
  onNavigateEnd,
  size = "default",
}: ChessBoardProps) {
  const safeFen = fen || DEFAULT_FEN;
  const board = useMemo(() => fenToBoard(safeFen), [safeFen]);
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);

  const handleSquareClick = (rankIndex: number, fileIndex: number) => {
    if (!onMoveAttempt) return;

    const square = toSquare(rankIndex, fileIndex);
    const piece = board[rankIndex]?.[fileIndex] ?? "";

    if (!selectedSquare) {
      if (piece) setSelectedSquare(square);
      return;
    }

    const selectedFile = FILES.indexOf(selectedSquare[0] ?? "a");
    const selectedRank = 8 - Number(selectedSquare[1] ?? 8);
    const selectedPiece = board[selectedRank]?.[selectedFile] ?? "";

    if (selectedSquare === square) {
      setSelectedSquare(null);
      return;
    }

    if (piece && isSameSide(selectedPiece, piece)) {
      setSelectedSquare(square);
      return;
    }

    onMoveAttempt(buildMoveAttempt(selectedSquare, square));
    setSelectedSquare(null);
  };

  return (
    <div className={cn("grid w-full gap-3", size === "large" ? "max-w-none" : "max-w-[420px]")} aria-label={title ?? "Chess board"}>
      {title ? <h3 className="text-base font-semibold text-foreground">{title}</h3> : null}
      <div className="grid aspect-square w-full grid-cols-8 overflow-hidden rounded-lg border border-border" role="img" aria-label={`Board position: ${safeFen}`} data-ply-index={currentPlyIndex ?? 0}>
        {board.map((rank, rankIndex) =>
          rank.map((piece, fileIndex) => {
            const isLight = (rankIndex + fileIndex) % 2 === 0;
            const square = toSquare(rankIndex, fileIndex);
            const imageCode = pieceToImageCode(piece);
            return (
              <button
                key={`${rankIndex}-${fileIndex}`}
                type="button"
                className={cn(
                  "grid aspect-square w-full place-items-center p-0 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                  isLight ? "bg-board-light text-board-light-piece" : "bg-board-dark text-board-dark-piece",
                  selectedSquare === square && "shadow-[inset_0_0_0_3px_rgb(var(--focus))]",
                )}
                aria-label={`Square ${square}${piece ? ` with ${piece}` : ""}`}
                onClick={() => handleSquareClick(rankIndex, fileIndex)}
              >
                {imageCode ? (
                  <span
                    aria-hidden="true"
                    className={cn("block h-[88%] w-[88%] bg-contain bg-center bg-no-repeat", size === "large" && "h-[92%] w-[92%]")}
                    style={{ backgroundImage: `url(${PIECE_BASE_URL}/${imageCode}.png)` } as CSSProperties}
                  />
                ) : null}
              </button>
            );
          }),
        )}
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Board navigation">
        <Button type="button" onClick={onNavigateStart} disabled={!onNavigateStart}>⏮</Button>
        <Button type="button" onClick={onNavigatePrev} disabled={!onNavigatePrev}>◀</Button>
        <Button type="button" onClick={onNavigateNext} disabled={!onNavigateNext}>▶</Button>
        <Button type="button" onClick={onNavigateEnd} disabled={!onNavigateEnd}>⏭</Button>
      </div>
      <small className="text-xs text-muted-foreground">FEN: {safeFen}</small>
    </div>
  );
}
