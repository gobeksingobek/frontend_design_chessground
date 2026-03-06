# ChessGround Web

## Repertoire import upload format

The web app supports repertoire import through `POST /repertoires/import`.

Accepted upload formats:

1. **Zip archive (`.zip`) containing PGN files**
   - The archive can include nested folders.
   - The backend recursively scans for `*.pgn` and `*.PGN` files.
2. **Single PGN file (`.pgn`)**

Not accepted:
- Database snapshots (`.db`, `.sqlite`, `.sql`) are not currently importable from the web endpoint.
- Archives without any PGN files.

Duplicate protection:
- Exact duplicate upload payloads are rejected with a conflict message.
- Duplicate lines inside the upload (already known canonical line path hashes) are skipped and reported in the import result.
