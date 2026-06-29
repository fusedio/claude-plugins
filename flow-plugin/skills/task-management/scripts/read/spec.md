# read

Return task records from the live app state file (`~/.openfused/app/state.json`,
or the directory named by `OPENFUSED_APP_DIR_STATE`).

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `project` | string | `""` | Project slug to filter on. Empty string returns all tasks across all projects. |

## Output

A list of task records (raw camelCase dicts from state.json), **newest-first by `createdAt`**.

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique task identifier |
| `project` | str | Project slug the task belongs to |
| `number` | int | Per-project task number |
| `title` | str | Human-readable task title |
| `description` | str | Task description (defaults to title when absent) |
| `status` | str | Task status (`pending`, `todo`, `in_progress`, `blocked`, `completed`, `failed`, `cancelled`) |
| `agentId` | str \| null | Agent assigned to the task |
| `createdBy` | str | Who created the task (`"user"` or an agent slug) |
| `createdAt` | str | ISO-8601 timestamp |
| `updatedAt` | str | ISO-8601 timestamp |
| `parentId` | str \| null | Parent task id, or null for root tasks |
| `workMode` | str | `"standard"` or `"planning"` |
| `blockedBy` | list[str] | Task ids this task is blocked by |

## Source

Reads `state.json` directly with stdlib (`json`, `os`); no third-party imports.
State path resolution:
- `OPENFUSED_APP_DIR_STATE` is a **directory** (not a file path); when set, used verbatim.
- Otherwise: `~/.openfused/app`.
- State file is always `<app_dir>/state.json`.

Missing file or JSON parse errors return an empty list (no exception raised).

## Constraints

- Stdlib-only; no third-party packages.
- Parameterized via `@udf def read(project: str = "")` (the injected decorator form).
- Preserves raw on-disk camelCase keys; does not reconstruct via any schema model.
