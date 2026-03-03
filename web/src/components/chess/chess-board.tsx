const PIECE_SYMBOLS: Record<string, string> = {
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

const DEFAULT_FEN = "rn1qkbnr/pppb1ppp/4p3/3p4/8/2N1PN2/PPPPBPPP/R1BQK2R w KQkq - 0 1";

function fenToBoard(fen: string): string[][] {
  const boardPart = fen.trim().split(/\s+/)[0] ?? "";
  const rows = boardPart.split("/");

  if (rows.length !== 8) {
    return fenToBoard(DEFAULT_FEN);
  }

  return rows.map((row) => {
    const squares: string[] = [];

    for (const char of row) {
      const emptyCount = Number(char);
      if (Number.isInteger(emptyCount) && emptyCount > 0) {
        for (let i = 0; i < emptyCount; i += 1) {
          squares.push("");
        }
        continue;
      }
      squares.push(char);
    }

    if (squares.length !== 8) {
      return Array.from({ length: 8 }, () => "");
    }

    return squares;
  });
}

export function ChessBoard({ fen, title }: { fen?: string; title?: string }) {
  const board = fenToBoard(fen || DEFAULT_FEN);

  return (
    <div className="board-wrap" aria-label={title ?? "Chess board"}>
      {title ? <h3>{title}</h3> : null}
      <div className="board" role="img" aria-label={`Board position: ${fen || DEFAULT_FEN}`}>
        {board.map((rank, rankIndex) =>
          rank.map((piece, fileIndex) => {
            const isLight = (rankIndex + fileIndex) % 2 === 0;
            return (
              <div key={`${rankIndex}-${fileIndex}`} className={`square ${isLight ? "light" : "dark"}`}>
                <span aria-hidden="true">{piece ? PIECE_SYMBOLS[piece] ?? "" : ""}</span>
              </div>
            );
          }),
        )}
      </div>
      <small>FEN: {fen || DEFAULT_FEN}</small>
    </div>
  );
}
