# Desktop capability contract

The PySide desktop client is an HTTP client over the same authenticated backend contracts as the web application. `AppController` may read optional local PGN directories only to package and upload their contents; it has no database or Stockfish access.

The desktop currently uses API contracts for:

- full, incremental, engine-only, matching, detail, per-game, and smoke analysis jobs;
- repertoire synchronization and game PGN upload;
- game, line, tree, position-game, monthly-time, time-pattern, rating-band, insight, and review reads;
- line moves, position lookup, mainline overrides, trainer state/sessions, review actions, and sideline requests;
- shared durable job polling and cancellation state.

Local settings are limited to backend URL/token, optional PGN upload directories, and piece assets. Canonical workspace settings are loaded from and saved to the backend.
