export interface EngineAnalysisResult {
  score_cp: number | null;
  depth: number | null;
  elapsed_ms: number;
}

export interface MoveDeltaResult {
  best: EngineAnalysisResult;
  candidate: EngineAnalysisResult;
  total_elapsed_ms: number;
}

const MATE_CP = 10_000;

function clampMate(mate: number): number {
  if (mate > 0) return MATE_CP;
  if (mate < 0) return -MATE_CP;
  return 0;
}

function parseInfoLine(line: string): { depth: number | null; scoreCp: number | null } {
  const depthMatch = line.match(/\bdepth\s+(\d+)/);
  const cpMatch = line.match(/\bscore\s+cp\s+(-?\d+)/);
  const mateMatch = line.match(/\bscore\s+mate\s+(-?\d+)/);

  const depth = depthMatch ? Number(depthMatch[1]) : null;
  let scoreCp: number | null = null;
  if (cpMatch) {
    scoreCp = Number(cpMatch[1]);
  } else if (mateMatch) {
    scoreCp = clampMate(Number(mateMatch[1]));
  }

  return { depth, scoreCp };
}

function normalizeWorkerLine(data: unknown): string | null {
  if (typeof data === "string") return data.trim();
  if (typeof data === "object" && data !== null) {
    const candidate = (data as { data?: unknown }).data;
    if (typeof candidate === "string") return candidate.trim();
  }
  return null;
}

function isValidUciMove(move: string): boolean {
  return /^[a-h][1-8][a-h][1-8][qrbn]?$/i.test(move.trim());
}

function sanitizeFen(fen: string): string {
  return fen.replace(/[\r\n]/g, " ").trim();
}

class StockfishClient {
  private worker: Worker | null = null;
  private readyPromise: Promise<void> | null = null;
  private lineSubscribers = new Set<(line: string) => void>();
  private queueTail: Promise<void> = Promise.resolve();
  private workerFailure: string | null = null;

  private ensureWorker(): Worker {
    if (typeof Worker === "undefined") {
      throw new Error("Web workers are unavailable in this environment");
    }
    if (this.worker) return this.worker;

    const worker = new Worker("/stockfish/stockfish.js");
    worker.addEventListener("message", (event: MessageEvent<unknown>) => {
      const line = normalizeWorkerLine(event.data);
      if (!line) return;
      for (const subscriber of this.lineSubscribers) {
        subscriber(line);
      }
    });
    worker.addEventListener("error", (event) => {
      this.workerFailure = event.message || "Stockfish worker failed";
    });

    this.worker = worker;
    return worker;
  }

  private post(command: string): void {
    const worker = this.ensureWorker();
    worker.postMessage(command);
  }

  private waitFor(
    predicate: (line: string) => boolean,
    timeoutMs: number,
    onLine?: (line: string) => void,
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      let done = false;
      const timeoutId = window.setTimeout(() => {
        cleanup();
        reject(new Error("Stockfish command timed out"));
      }, timeoutMs);

      const cleanup = () => {
        if (done) return;
        done = true;
        window.clearTimeout(timeoutId);
        this.lineSubscribers.delete(handler);
      };

      const handler = (line: string) => {
        if (this.workerFailure) {
          cleanup();
          reject(new Error(this.workerFailure));
          return;
        }
        onLine?.(line);
        if (!predicate(line)) return;
        cleanup();
        resolve();
      };

      this.lineSubscribers.add(handler);
    });
  }

  private async sendAndWait(
    command: string,
    predicate: (line: string) => boolean,
    timeoutMs: number,
    onLine?: (line: string) => void,
  ): Promise<void> {
    const wait = this.waitFor(predicate, timeoutMs, onLine);
    this.post(command);
    await wait;
  }

  private async ensureReady(): Promise<void> {
    if (this.readyPromise) {
      await this.readyPromise;
      return;
    }
    this.readyPromise = (async () => {
      await this.sendAndWait("uci", (line) => line === "uciok", 4_000);
      await this.sendAndWait("isready", (line) => line === "readyok", 4_000);
    })();
    try {
      await this.readyPromise;
    } catch (error) {
      this.readyPromise = null;
      this.disposeWorker();
      throw error;
    }
  }

  private async runGo(command: string, timeoutMs: number): Promise<EngineAnalysisResult> {
    let deepest: number | null = null;
    let scoreCp: number | null = null;
    const startedAt = Date.now();

    await this.sendAndWait(
      command,
      (line) => line.startsWith("bestmove"),
      timeoutMs,
      (line) => {
        if (!line.startsWith("info ")) return;
        const parsed = parseInfoLine(line);
        if (parsed.depth !== null) {
          deepest = parsed.depth;
        }
        if (parsed.scoreCp !== null) {
          scoreCp = parsed.scoreCp;
        }
      },
    );

    return {
      score_cp: scoreCp,
      depth: deepest,
      elapsed_ms: Date.now() - startedAt,
    };
  }

  private async runExclusive<T>(operation: () => Promise<T>): Promise<T> {
    const previous = this.queueTail;
    let release: () => void = () => {};
    this.queueTail = new Promise<void>((resolve) => {
      release = resolve;
    });
    await previous;
    try {
      return await operation();
    } finally {
      release();
    }
  }

  private disposeWorker(): void {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    this.workerFailure = null;
  }

  async analyzeMoveDelta(fen: string, candidateMove: string, depth: number, moveTimeMs: number): Promise<MoveDeltaResult> {
    const fenText = sanitizeFen(fen);
    const candidate = candidateMove.trim().toLowerCase();
    if (!fenText) throw new Error("FEN is required for quick eval");
    if (!isValidUciMove(candidate)) throw new Error("Candidate move must be valid UCI");

    return this.runExclusive(async () => {
      await this.ensureReady();

      const perGoTimeout = Math.max(moveTimeMs + 5_000, 6_000);
      const totalStartedAt = Date.now();

      this.post("ucinewgame");
      await this.sendAndWait("isready", (line) => line === "readyok", 4_000);

      this.post(`position fen ${fenText}`);
      const best = await this.runGo(`go depth ${depth} movetime ${moveTimeMs}`, perGoTimeout);

      this.post(`position fen ${fenText}`);
      const candidateResult = await this.runGo(
        `go depth ${depth} movetime ${moveTimeMs} searchmoves ${candidate}`,
        perGoTimeout,
      );

      return {
        best,
        candidate: candidateResult,
        total_elapsed_ms: Date.now() - totalStartedAt,
      };
    });
  }
}

export const stockfishClient = new StockfishClient();
