"use client";

import { CSSProperties, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

const FILES = "abcdefgh";
const DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const DEFAULT_PIECE_THEME_PATH = "/pieces/neo";

type Square = string;

interface ChessBoardProps {
  fen?: string;
  title?: string;
  subtitle?: string;
  currentPlyIndex?: number;
  onMoveAttempt?: (move: { uci: string; from: string; to: string }) => void;
  onNavigateNext?: () => void;
  onNavigatePrev?: () => void;
  onNavigateStart?: () => void;
  onNavigateEnd?: () => void;
  size?: "default" | "large";
  showCoordinates?: boolean;
  legalTargets?: string[];
  lastMove?: { from: string; to: string } | null;
  pieceAssetBasePath?: string;
}

interface ParsedFen {
  board: string[][];
  activeColor: "w" | "b";
  halfmoveClock: number;
  fullmoveNumber: number;
}

function toSquare(rankIndex: number, fileIndex: number): Square {
  return `${FILES[fileIndex] ?? "a"}${8 - rankIndex}`;
}

function squareToCoords(square: string): { rankIndex: number; fileIndex: number } | null {
  const fileIndex = FILES.indexOf(square[0] ?? "");
  const rank = Number(square[1] ?? "");
  if (fileIndex < 0 || rank < 1 || rank > 8) return null;
  return { rankIndex: 8 - rank, fileIndex };
}

function parseFen(fen: string): ParsedFen {
  const [boardPart = "", activeColorPart = "w", _castling, _ep, halfmovePart = "0", fullmovePart = "1"] = fen.trim().split(/\s+/);
  const rows = boardPart.split("/");

  if (rows.length !== 8) return parseFen(DEFAULT_FEN);

  const board = rows.map((row) => {
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

  return {
    board,
    activeColor: activeColorPart === "b" ? "b" : "w",
    halfmoveClock: Number.isFinite(Number(halfmovePart)) ? Number(halfmovePart) : 0,
    fullmoveNumber: Number.isFinite(Number(fullmovePart)) ? Number(fullmovePart) : 1,
  };
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

function sideLabel(side: "w" | "b"): string {
  return side === "w" ? "White to move" : "Black to move";
}

function pieceColor(piece: string): "w" | "b" | null {
  if (!piece) return null;
  return piece === piece.toUpperCase() ? "w" : "b";
}

function findKing(board: string[][], side: "w" | "b"): Square | null {
  const target = side === "w" ? "K" : "k";
  for (let rankIndex = 0; rankIndex < 8; rankIndex += 1) {
    for (let fileIndex = 0; fileIndex < 8; fileIndex += 1) {
      if (board[rankIndex]?.[fileIndex] === target) return toSquare(rankIndex, fileIndex);
    }
  }
  return null;
}

function attacksSquare(board: string[][], from: { rankIndex: number; fileIndex: number }, piece: string, target: { rankIndex: number; fileIndex: number }): boolean {
  const rankDelta = target.rankIndex - from.rankIndex;
  const fileDelta = target.fileIndex - from.fileIndex;
  const absRank = Math.abs(rankDelta);
  const absFile = Math.abs(fileDelta);
  const color = pieceColor(piece);
  const kind = piece.toLowerCase();

  if (!color) return false;

  if (kind === "p") {
    const direction = color === "w" ? -1 : 1;
    return rankDelta === direction && absFile === 1;
  }

  if (kind === "n") return (absRank === 2 && absFile === 1) || (absRank === 1 && absFile === 2);
  if (kind === "k") return absRank <= 1 && absFile <= 1;

  const isDiagonal = absRank === absFile && absRank > 0;
  const isStraight = (rankDelta === 0 && absFile > 0) || (fileDelta === 0 && absRank > 0);
  if ((kind === "b" && !isDiagonal) || (kind === "r" && !isStraight) || (kind === "q" && !(isDiagonal || isStraight))) return false;

  const stepRank = Math.sign(rankDelta);
  const stepFile = Math.sign(fileDelta);
  let currentRank = from.rankIndex + stepRank;
  let currentFile = from.fileIndex + stepFile;
  while (currentRank !== target.rankIndex || currentFile !== target.fileIndex) {
    if (board[currentRank]?.[currentFile]) return false;
    currentRank += stepRank;
    currentFile += stepFile;
  }
  return true;
}

export function isKingInCheck(fen: string): Square | null {
  const { board, activeColor } = parseFen(fen || DEFAULT_FEN);
  const kingSquare = findKing(board, activeColor);
  const kingCoords = kingSquare ? squareToCoords(kingSquare) : null;
  if (!kingSquare || !kingCoords) return null;

  for (let rankIndex = 0; rankIndex < 8; rankIndex += 1) {
    for (let fileIndex = 0; fileIndex < 8; fileIndex += 1) {
      const piece = board[rankIndex]?.[fileIndex] ?? "";
      if (!piece || pieceColor(piece) === activeColor) continue;
      if (attacksSquare(board, { rankIndex, fileIndex }, piece, kingCoords)) return kingSquare;
    }
  }

  return null;
}

function IconChevronFirst() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M11 17l-5-5 5-5" /><path d="M18 17l-5-5 5-5" /></svg>;
}
function IconChevronLeft() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M15 18l-6-6 6-6" /></svg>;
}
function IconChevronRight() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M9 18l6-6-6-6" /></svg>;
}
function IconChevronLast() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M13 17l5-5-5-5" /><path d="M6 17l5-5-5-5" /></svg>;
}

export function ChessBoard({
  fen,
  title,
  subtitle,
  currentPlyIndex,
  onMoveAttempt,
  onNavigateNext,
  onNavigatePrev,
  onNavigateStart,
  onNavigateEnd,
  size = "default",
  showCoordinates = true,
  legalTargets,
  lastMove,
  pieceAssetBasePath = DEFAULT_PIECE_THEME_PATH,
}: ChessBoardProps) {
  const safeFen = fen || DEFAULT_FEN;
  const { board, activeColor, halfmoveClock, fullmoveNumber } = useMemo(() => parseFen(safeFen), [safeFen]);
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const checkSquare = useMemo(() => isKingInCheck(safeFen), [safeFen]);
  const legalTargetSet = useMemo(() => new Set(legalTargets ?? []), [legalTargets]);

  useEffect(() => {
    setSelectedSquare(null);
  }, [safeFen]);

  const handleSquareClick = (rankIndex: number, fileIndex: number) => {
    if (!onMoveAttempt) return;

    const square = toSquare(rankIndex, fileIndex);
    const piece = board[rankIndex]?.[fileIndex] ?? "";

    if (!selectedSquare) {
      if (piece && pieceColor(piece) === activeColor) setSelectedSquare(square);
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
    <Card
      className={cn(
        "w-full gap-4 overflow-hidden border-border/80 bg-gradient-to-br from-card via-card to-elevated/80",
        size === "large" ? "max-w-none" : "max-w-[480px]",
      )}
      aria-label={title ?? "Chess board"}
    >
      <div className="flex flex-col gap-3 border-b border-border/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="grid gap-1">
          {title ? <h3 className="text-base font-semibold tracking-tight text-foreground sm:text-lg">{title}</h3> : null}
          <p className="text-sm text-muted-foreground">{subtitle ?? "Study the current position, inspect move context, and navigate through the line."}</p>
        </div>
        <div className="grid gap-2 sm:justify-items-end">
          <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-muted-foreground">
            <span className="rounded-full border border-border/70 bg-background/80 px-2.5 py-1">{sideLabel(activeColor)}</span>
            <span className="rounded-full border border-border/70 bg-background/80 px-2.5 py-1">Move {fullmoveNumber}</span>
            <span className="rounded-full border border-border/70 bg-background/80 px-2.5 py-1">Ply {currentPlyIndex ?? 0}</span>
            <span className="rounded-full border border-border/70 bg-background/80 px-2.5 py-1">Halfmove {halfmoveClock}</span>
          </div>
          <div className="flex items-center gap-1 rounded-full border border-border/70 bg-background/70 p-1 shadow-sm" role="group" aria-label="Board navigation">
            <Button type="button" size="icon" variant="ghost" className="rounded-full" onClick={onNavigateStart} disabled={!onNavigateStart} aria-label="Jump to start"><IconChevronFirst /></Button>
            <Button type="button" size="icon" variant="ghost" className="rounded-full" onClick={onNavigatePrev} disabled={!onNavigatePrev} aria-label="Previous move"><IconChevronLeft /></Button>
            <div className="h-6 w-px bg-border/80" aria-hidden="true" />
            <Button type="button" size="icon" variant="ghost" className="rounded-full" onClick={onNavigateNext} disabled={!onNavigateNext} aria-label="Next move"><IconChevronRight /></Button>
            <Button type="button" size="icon" variant="ghost" className="rounded-full" onClick={onNavigateEnd} disabled={!onNavigateEnd} aria-label="Jump to end"><IconChevronLast /></Button>
          </div>
        </div>
      </div>

      <div className={cn("relative mx-auto w-full", size === "large" ? "max-w-[min(72vh,760px)]" : "max-w-[min(88vw,460px)]")}>
        <div
          className="chess-board-shell relative aspect-square w-full rounded-[1.25rem] border border-border/80 bg-[rgb(var(--board-frame))] p-3 shadow-board"
          role="img"
          aria-label={`Board position: ${safeFen}`}
          data-ply-index={currentPlyIndex ?? 0}
        >
          <div className="absolute inset-x-5 top-2 flex justify-between text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground/80" aria-hidden="true">
            {showCoordinates ? FILES.split("").map((file) => <span key={`top-${file}`}>{file}</span>) : null}
          </div>
          <div className="absolute inset-x-5 bottom-2 flex justify-between text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground/80" aria-hidden="true">
            {showCoordinates ? FILES.split("").map((file) => <span key={`bottom-${file}`}>{file}</span>) : null}
          </div>
          <div className="absolute inset-y-5 left-2 flex flex-col justify-between text-[10px] font-semibold tracking-[0.22em] text-muted-foreground/80" aria-hidden="true">
            {showCoordinates ? Array.from({ length: 8 }, (_, index) => <span key={`left-${8 - index}`}>{8 - index}</span>) : null}
          </div>
          <div className="absolute inset-y-5 right-2 flex flex-col justify-between text-[10px] font-semibold tracking-[0.22em] text-muted-foreground/80" aria-hidden="true">
            {showCoordinates ? Array.from({ length: 8 }, (_, index) => <span key={`right-${8 - index}`}>{8 - index}</span>) : null}
          </div>

          <div className="grid aspect-square w-full grid-cols-8 overflow-hidden rounded-[0.95rem] border border-[rgb(var(--board-grid-border))] shadow-[inset_0_0_0_1px_rgba(var(--board-grid-shadow))]">
            {board.map((rank, rankIndex) =>
              rank.map((piece, fileIndex) => {
                const isLight = (rankIndex + fileIndex) % 2 === 0;
                const square = toSquare(rankIndex, fileIndex);
                const imageCode = pieceToImageCode(piece);
                const isSelected = selectedSquare === square;
                const isLegalTarget = legalTargetSet.has(square);
                const isLastMoveSquare = lastMove?.from === square || lastMove?.to === square;
                const isLastMoveFrom = lastMove?.from === square;
                const isLastMoveTo = lastMove?.to === square;
                const isCheck = checkSquare === square;

                return (
                  <button
                    key={`${rankIndex}-${fileIndex}`}
                    type="button"
                    className={cn(
                      "group relative grid aspect-square w-full place-items-center overflow-hidden p-0 transition-transform duration-150 ease-out focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus hover:z-[1] hover:scale-[1.01]",
                      isLight ? "bg-board-light text-board-light-piece" : "bg-board-dark text-board-dark-piece",
                      isSelected && "ring-0 before:absolute before:inset-[8%] before:rounded-xl before:border-2 before:border-[rgb(var(--board-selected-ring))] before:bg-[rgb(var(--board-selected-fill))] before:content-['']",
                      isLastMoveSquare && "after:absolute after:inset-[6%] after:rounded-xl after:border after:border-[rgb(var(--board-last-move-border))] after:content-['']",
                      isCheck && "before:absolute before:inset-[8%] before:rounded-full before:bg-[radial-gradient(circle,rgba(248,113,113,0.9)_0%,rgba(248,113,113,0.18)_48%,transparent_72%)] before:content-['']",
                    )}
                    aria-label={`Square ${square}${piece ? ` with ${piece}` : ""}`}
                    onClick={() => handleSquareClick(rankIndex, fileIndex)}
                  >
                    {isLastMoveFrom ? <span className="absolute inset-[10%] rounded-xl bg-[rgb(var(--board-last-move-from))] opacity-85" aria-hidden="true" /> : null}
                    {isLastMoveTo ? <span className="absolute inset-[10%] rounded-xl bg-[rgb(var(--board-last-move-to))] opacity-85" aria-hidden="true" /> : null}
                    {isLegalTarget ? (
                      piece ? <span className="absolute inset-[20%] rounded-full border-4 border-[rgb(var(--board-legal-target))] opacity-80" aria-hidden="true" /> : <span className="absolute h-[22%] w-[22%] rounded-full bg-[rgb(var(--board-legal-target))] opacity-80" aria-hidden="true" />
                    ) : null}
                    {showCoordinates && fileIndex === 0 ? <span className={cn("pointer-events-none absolute left-1 top-1 text-[9px] font-semibold", isLight ? "text-[rgb(var(--board-coordinate-light))]" : "text-[rgb(var(--board-coordinate-dark))]")}>{8 - rankIndex}</span> : null}
                    {showCoordinates && rankIndex === 7 ? <span className={cn("pointer-events-none absolute bottom-1 right-1 text-[9px] font-semibold lowercase", isLight ? "text-[rgb(var(--board-coordinate-light))]" : "text-[rgb(var(--board-coordinate-dark))]")}>{FILES[fileIndex]}</span> : null}
                    {imageCode ? (
                      <span
                        aria-hidden="true"
                        className={cn(
                          "chess-piece relative z-[1] block h-[88%] w-[88%] bg-contain bg-center bg-no-repeat drop-shadow-[0_8px_10px_rgba(15,23,42,0.18)] transition-transform duration-200 ease-out group-hover:scale-[1.04]",
                          size === "large" && "h-[92%] w-[92%]",
                          isSelected && "scale-[1.06]",
                        )}
                        style={{ backgroundImage: `url(${pieceAssetBasePath}/${imageCode}.svg)` } as CSSProperties}
                      />
                    ) : null}
                  </button>
                );
              }),
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-1">
        <small className="text-xs text-muted-foreground">FEN: {safeFen}</small>
      </div>
    </Card>
  );
}
