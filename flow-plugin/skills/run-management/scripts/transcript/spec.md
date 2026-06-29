# transcript — a run's NDJSON event log

```
transcript(run_id: str = "") -> list[dict]
```

Reads `<app_dir>/runs/<run_id>.ndjson` and returns the run's `RunEvent`
envelopes in file order. `<app_dir>` is `$OPENFUSED_APP_DIR_STATE` (verbatim) or
`~/.openfused/app` — the same `APP_DIR` under which the
Express launcher writes `runs/<id>.ndjson`.

Each line of the file is one `RunEvent`:

```json
{"runId": "run_…", "seq": 0, "type": "…", "payload": { … }}
```

`payload` is a nested object whose shape depends on `type`. Because the result
is non-tabular, **prefer the UDF endpoint** for this UDF:

```
POST /api/exec/udf?workspace=_core&project=run-management
{"udf": "transcript", "overrides": {"run_id": "run_…"}}
```

## Behavior

- Empty `run_id` → `[]`.
- A `run_id` whose resolved path would escape `runs/` (traversal via `..`, an
  absolute path, or a symlink) → `[]`. The path is confined to the real `runs/`
  directory before opening, since `run_id` is caller-controlled.
- Missing transcript file → `[]` (not an error). A run that is queued but never
  launched has no file yet.
- **Snapshot, not a stream.** Returns the events written so far; the caller
  re-resolves to refresh. There is no live streaming — that stays the app's SSE
  channel (`GET /api/runs/:id/events`), which the widget layer cannot subscribe
  to.
- **Torn-line tolerance.** The NDJSON is append-as-you-go, so a crash mid-run can
  leave a torn final line. Invalid-JSON lines are skipped and the valid prefix is
  returned — mirroring the Express `replayEvents`.

## Notes

- Read-only, stdlib-only; reads the file directly (the exec sandbox shadows the
  real `fused` package with a shim).
