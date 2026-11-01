# Phase 3 — ingestion and retrieval

Date: 2026-10-30 (Australia/Sydney). **Implementation and automated/retrieval validation complete. Configured corpus has one explicitly reported invalid input; full-corpus freshness is therefore incomplete. Phase 4 has not started.**

## Delivered scope

SQLite schema 1 with persistent document IDs, immutable canonical revision records, block/note tables and FTS5; recursive source discovery and unchanged-file skipping; per-document atomic ingestion with old revisions retained; `ingest`, `status`, `search`, `passage`, `notes` and stdout `export`; explicit source freshness on every retrieval; versioned JSON and readable output; full editorial marks/notes/provenance carried into retrieval.

Added src/scholium/storage.py, indexing.py, search.py and tests/test_index.py. Updated CLI/package metadata to 0.3.0 and relevant documentation. Added docs/CLI.md and INDEX_SCHEMA.md. Real-corpus audit artifacts are private in .verify/phase3; runtime index is in the user's configured data directory. No source DOCX files were modified.

## Actual validation

- `.venv/bin/python -m pytest -q`: **55 passed** (final run 0.92 seconds). Includes 18 Phase 3 cases plus the 37 prior cases.
- `.venv/bin/ruff check .`: all checks passed. `.venv/bin/ruff format --check .`: 21 files already formatted (including build copies).
- `.venv/bin/python -m pip check`: no broken requirements.
- Editable installation updated to 0.3.0; independent non-editable wheel installation in .verify/clean succeeded, including reinstall after final changes.
- Installed CLI run from a different working directory with explicit book configuration: status, search, passage, notes and JSON export all returned valid JSON. Expected exit 1 correctly reflected the known invalid source while retrieval returned usable evidence.
- Database content hash and modification timestamp were identical before/after those retrieval commands.
- Synthetic tests: same term across chapters and notes, heading/note provenance, idempotence, stale detection, changed revision search replacement, explicit historical access, corrupt/missing-source retention, Unicode/diacritic behavior, safe literal queries, editorial markings, overlapping roots/lock files, duplicate filenames, explicit-file scope, unknown schema protection, byte-revert identity, and no-file-creation read operations.
- Recovery tests include rollback after FTS insertion, source mutation before commit, and an abruptly terminated subprocess with an uncommitted multi-megabyte SQLite write. A subsequent writable ingest recovered the journal, retained the previous revision, and passed integrity_check.
- Initial lint found one unused test import; fixed before final validation. No unresolved automated failures.

## Configured corpus results

18 candidate documents found (Word ~$ lock files skipped): **17 successfully indexed**, **1 rejected**. Indexed content: **2,168 blocks, 551 notes, 2,719 search records**. SQLite integrity_check returned ok; foreign_key_check returned no violations.

The user requested a retry. Retry returned **17 unchanged, 1 error**: `Contents.docx` is 162 bytes and is not a DOCX ZIP archive. It was not deleted, renamed or silently excluded. The distinct `0-Contents.docx` successfully indexed. This rejected input remains visible in status and retrieval freshness. It requires a valid DOCX replacement or a user decision about whether it belongs in the source folder; scholium cannot infer its intended contents.

Search validation:

| Query | Returned hits | Distinct chapters represented |
|---|---:|---:|
| Weimar | 100 (limit reached; not a total count) | 16 |
| Goethe | 13 | 6 |
| Hirschfeld | 62 | 14 |
| Müller | 39 | 10 |
| Homosexualität | 22 | 7 |

For each query, retrieved the first five hits through passage or notes and verified exact text/revision agreement. Also compared those **25 records across 11 source files** against fresh read-only extraction from their cited source paths, including hashes, record IDs, note anchors and formatting metadata. All matched. All 18 original source hashes matched the pre-ingestion snapshot after validation. This validates storage/retrieval provenance; it is not a new visual acceptance of every chapter or external scholarly verification.

Existing extraction qualifications are preserved in results. The corpus includes one chapter with style-defined editorial formatting and another with hidden text. Four unsupported-block warnings identify bookmarkEnd markers, rather than dropped body paragraphs. Automatic list numbering and image interpretation limitations remain. Current source hashes do not erase these fidelity limitations.

## Acceptance and reproducible demonstration

The assistant performed routine retrieval checks, following the user's preference not to repeat tedious manual comparisons. Optional author exploration from the configured book workspace:

```sh
scholium --version
scholium status
scholium search "Goethe" --limit 3
scholium notes --chapter "1a-Introduction5" --note endnote:1
scholium passage --chapter "1a-Introduction5" --block 2
```

Expected: version 0.3.0; status/retrieval warns about Contents.docx; real passages/notes have explicit revision locators. Block 2 of the reviewed introduction retains strikethrough labels. Exit 1 with these results is deliberate incomplete-freshness reporting, not a lost database or failed search. Do not require the author to re-check every paragraph/note to approve the software phase.

## Limits and recommendation

Read-only freshness hashes sources at command time; no watcher runs after Word saves. No rename matching, revision diff command, retention cleanup, automated backup/restore, semantic search or AI analysis. Explicit old-revision retrieval requires a previously obtained revision ID. Unknown database versions are rejected unchanged; version 1 is the first database schema. No performance claim beyond this corpus and the executed tests. A damaged SQLite database is reported; automatic repair is not attempted.

The index is useful now, with the incomplete-source and extraction warnings above. Resolve the invalid input when appropriate. Next recommended stage, after user authorization: Phase 4 save detection, reconciliation scheduling and revision comparison. No Phase 4 work has begun.
