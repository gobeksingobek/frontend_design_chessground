"use client";

const PIECES: Record<string, string> = {
  p: "♟",
  r: "♜",
  n: "♞",
  b: "♝",
  q: "♛",
  k: "♚",
  P: "♙",
  R: "♖",
  N: "♘",
  B: "♗",
  Q: "♕",
  K: "♔",
};

function boardFromFen(fen: string): string[][] {
  const placement = fen.trim().split(/\s+/)[0] ?? "";
  const rows = placement.split("/");
  if (rows.length !== 8) return Array.from({ length: 8 }, () => Array(8).fill(""));

  return rows.map((row) => {
    const squares: string[] = [];
    for (const char of row) {
      const empty = Number(char);
      if (Number.isInteger(empty) && empty > 0) {
        for (let i = 0; i < empty; i += 1) squares.push("");
      } else {
        squares.push(PIECES[char] ?? "");
      }
    }
    return squares.slice(0, 8);
  });
}

export function ChessBoard({ fen, title }: { fen: string; title?: string }) {
  const board = boardFromFen(fen);

  return (
    <div className="chess-board-wrap" aria-label={title ?? "Position"}>
      {title ? <h4>{title}</h4> : null}
      <div className="chess-board">
        {board.map((row, rankIndex) =>
          row.map((piece, fileIndex) => {
            const dark = (rankIndex + fileIndex) % 2 === 1;
            return (
              <div key={`${rankIndex}-${fileIndex}`} className={`square ${dark ? "dark" : "light"}`}>
                {piece}
              </div>
            );
          }),
        )}
      </div>
      <small>FEN: {fen}</small>
    </div>
  );
}
