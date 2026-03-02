Place real Stockfish WASM web assets in this folder for browser quick-eval.

Minimum expected files:
- `stockfish.js` (worker entry)
- companion `.wasm` file required by that worker build

The committed `stockfish.js` is a placeholder shim that keeps UI flow functional
but returns no engine score. Replace it with a real Stockfish WASM build to
enable non-null `cpl_estimate` values.
