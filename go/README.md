# Go service — shadowcode-preview

High-concurrency localhost service (Go stdlib only, no external
dependencies): live browser-preview server + fast file search.

## Build — DEFERRED if no Go toolchain

```bash
cd ~/workspace/shadowcode/go
go build -o shadowcode-preview ./cmd/shadowcode-preview
```

**Status in this environment (cycle 5): `go` is not installed,
and installing a toolchain outside the project needs user
approval — so the build was NOT run here and is logged in
`../MORNING_APPROVALS.md`. The source is real, stdlib-only, and
ready to build once Go is installed. Do not claim a Go binary
exists until `go build` has actually run.**

## Run (once built)

```bash
./shadowcode-preview --workdir ../test-workspace --port 8765
# open http://localhost:8765
```

## Endpoints (127.0.0.1 only)

- `GET /health` → `{"ok": true}`
- `GET /state.json` → `{title, url, driver, has_screenshot}`
- `POST /state` (JSON `{title,url,driver}`) → update state
- `GET /shot.png` → latest PNG, or 404
- `POST /shot` (PNG body, ≤10 MiB) → replace screenshot
- `POST /takeover` / `POST /handback` → driver=user/agent
- `GET /search?q=...` → JSON hits from `internal/search`
  (case-insensitive, skips .git/node_modules/dist/__pycache__,
  skips files >1 MiB, capped at 100, ranked by match count)
- `GET /` → `../web/index.html` preview frontend

The Python browser thread serves the same `/state.json` /
`/shot.png` shapes today, so the TS TUI works with either server.
