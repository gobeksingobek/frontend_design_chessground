/* eslint-disable no-restricted-globals */
// Placeholder worker shim. Replace this file with a real Stockfish WASM worker build
// (plus its .wasm companion file) to enable quick CPL estimates.

function reply(line) {
  self.postMessage(line);
}

self.onmessage = (event) => {
  const raw = typeof event.data === "string" ? event.data.trim() : "";
  if (!raw) return;

  if (raw === "uci") {
    reply("id name Stockfish WASM placeholder");
    reply("id author ChessGround");
    reply("uciok");
    return;
  }

  if (raw === "isready") {
    reply("readyok");
    return;
  }

  if (raw === "ucinewgame" || raw.startsWith("position ")) {
    return;
  }

  if (raw.startsWith("go ")) {
    reply("bestmove 0000");
    return;
  }

  if (raw === "quit") {
    self.close();
  }
};
