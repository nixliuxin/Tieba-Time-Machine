# Tieba-Time-Machine — Project Conventions

This file is auto-loaded by Cursor when the agent works anywhere inside
this repository. It defines project-wide rules, layout, and pipeline.

For format-specific knowledge, see `.cursor/rules/`:

- `english-only.mdc` — language policy
- `no-cursor-attribution.mdc` — commit hygiene
- `no-personal-info.mdc` — no personal stats/paths/forums in published content
- `versioning.mdc` — SemVer policy

## What this repo is

Open-source monorepo for **Tieba-Time-Machine** — a toolkit that archives Baidu Tieba
(百度贴吧) forums and provides an offline reader. Ships a unified CLI
(`tieba_time_machine/cli.py`), an offline ETL pipeline (`tools/`), a FastAPI reader
backend (`server/`), and a React single-page viewer (`frontend/`).

## Repo layout

| Path | Role |
|---|---|
| `scraper/src/` | Core scrape engine (modules, services, API wrappers, DB) |
| `scraper/backup_forum.py` | Batch forum scraper — collects tids then downloads all threads |
| `scraper/backup_user.py` | Batch user scraper — collects a user's threads then downloads |
| `scraper/backup_lib.py` | Shared batch infrastructure (concurrency, logging, locking) |
| `tools/merge_archive.py` | Merge per-thread content.db + JSON into unified master.db |
| `tools/pack_media.py` | Pack media files into uncompressed tar with index |
| `tools/par2_protect.py` | Generate PAR2 parity files for tar archives |
| `tools/run_all.py` | Orchestrate merge → pack → par2 in sequence |
| `tools/schema.sql` | SQLite schema for master.db (includes FTS5) |
| `server/main.py` | FastAPI backend serving master.db + media from tar |
| `frontend/` | React + Vite + TanStack Router/Query offline SPA |
| `tieba_time_machine/cli.py` | Unified CLI entry point (`tieba` command) |
| `docs/` | Technical documentation |

## Hard rules

1. **English only** in code, comments, variable names, log messages,
   CLI output, and error messages. The only exceptions are:
   - `README.md` (Chinese primary README)
   - Frontend viewer UI labels (Tieba is a Chinese product)
   - Tieba API parameter values that must match upstream protocol
2. **No AI attribution** in commit messages. No `Co-authored-by: Cursor`
   or similar trailers.
3. **Never commit secrets.** `tieba_auth.json`, BDUSS values, cookies,
   and any file containing authentication tokens must be gitignored.
4. **Resume by default.** Every batch operation must be checkpoint-based.
   Interrupted runs resume where they left off, never re-download
   already validated data.
5. **No hardcoded local paths** in committed code. Use environment
   variables or CLI arguments for data directories. Paths like
   `L:\DATA` or `D:\archives` must never appear in source.
6. **Per-forum isolation.** Each forum produces its own independent
   archive (master.db + media.tar + par2). The reader loads one or
   more forums dynamically.
7. **No personal information in published content.** Release notes, docs,
   commit messages, CLI help examples, and comments must not include real
   backup statistics, local/cloud paths, personal forum names, or thread IDs
   from a personal run. Use generic placeholders. Personal batch scripts
   belong in gitignored `tools/_*.py` only. See `.cursor/rules/no-personal-info.mdc`.

## Pipeline overview

```
Scrape (backup_forum.py)
    → per-thread folders with content.db + JSON + media
        → merge_archive.py → master.db (per forum)
            → pack_media.py → media.tar + media_index.json
                → par2_protect.py → *.par2
                    → server/main.py serves via REST API
                        → frontend/ renders in browser
```

## Error handling conventions

- Use descriptive error messages that include context (forum name,
  tid, file path).
- Batch operations must log failures and continue, not abort the
  entire run for a single thread failure.
- Never silently swallow errors with empty `except: pass`.

## Linked references

- English-only policy → `.cursor/rules/english-only.mdc`
- Commit hygiene → `.cursor/rules/no-cursor-attribution.mdc`
- Versioning → `.cursor/rules/versioning.mdc`
- No personal info → `.cursor/rules/no-personal-info.mdc`
