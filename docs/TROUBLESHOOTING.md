# Troubleshooting

For command-not-found and PATH problems see [installation and maintenance](OPERATIONS.md).

- No configuration: run `scholium setup .` in the intended book folder, or pass `--config FILE` before `doctor`.
- No sources: edit manuscript.source_dirs; setup intentionally starts with an empty list.
- Configuration rejected: check TOML syntax, schema_version = 1, table/key names, string lists and non-overlapping source/data paths. Unknown keys are rejected to catch typos. Error messages do not echo configuration contents.
- Source unavailable: check the folder path and permissions. Sync placeholder readiness is not validated in doctor.
- FTS5 unavailable: use a Python installation whose SQLite includes FTS5. Doctor tests an in-memory table.
- Setup kept existing: intentional; edit the file yourself. It will not overwrite existing configuration or a symlink.

Standalone extraction, database ingestion/search and freshness status are available. Foreground watching and verified backup/restore commands are available.

Extraction errors:

- Existing output: choose a new --output directory. Previous exports are preserved.
- Tracked changes: resolve them in an author-reviewed copy using Word, then extract that copy.
- Missing/unreferenced notes: compare the note apparatus in Word; do not use an incomplete derivative. Report the failure with a synthetic reproducer where possible.
- Source changed: wait until Word has finished saving, then retry.
- Malformed/oversized/unsupported DOCX: check that the file is fully downloaded and opens normally in Word. Save a separate ordinary DOCX copy if appropriate. Never repair originals automatically.
- Output locked after process termination: ensure no extraction is running, then remove only the corresponding `.OUTPUTNAME.scholium-lock` file or choose a new directory. Abrupt termination may also leave a private `.scholium-export-*` temporary directory beside the output; it can be removed after confirming no extraction is using it. Normal handled failures clean these up.

Indexing and retrieval:

- Exit 1 with valid results: inspect freshness/scan errors. A corrupt or missing source makes corpus evidence incomplete; previous good revisions remain accessible.
- Invalid DOCX archive: check the actual file in Word. Tiny temporary/placeholder files may have a .docx extension without DOCX contents. scholium skips ~$ lock files but does not silently ignore other invalid files.
- Unknown chapter: use the exact filename-stem key (or document UUID) shown by status. Duplicate stems have distinct suffixed keys.
- No search match: matching is literal AND terms with diacritics preserved. Try fewer terms and read complete passages/notes.
- SQLite busy/error after abrupt interruption: stop competing writers and rerun ingest to allow SQLite's writable rollback recovery. Read-only commands do not repair journals. For persistent corruption, retain the damaged files and use backup-check/restore into a new data directory. See OPERATIONS.md. If no verified backup exists, rebuilding from originals cannot restore lost history or analyses.
- Unsupported schema: use the matching scholium version; never lower user_version manually or delete the index as an automatic fix.
- Export is historical/stale: re-ingest the source if appropriate. Export does not itself update the index.

Phase 4:

- Search did not refresh: ensure `watch` is running with the intended configuration. Wait for the stability interval; use `status` to see failures. Run `ingest --all` for manual reconciliation. --poll remains usable if native notifications fail.
- Repeated partial saves: watcher waits/retries; old good evidence stays available. After the bounded retries, change the file or restart watch to retry unchanged failed bytes.
- Another watcher holds this book: stop the existing foreground process. Do not delete watch.lock while it is held. An old lock file without a live kernel lock does not prevent startup.
- Schema 1 migration required: run ingest --all or watch. A private backup is made before the additive upgrade. Read-only commands never upgrade automatically.
- Rename not linked: edited/ambiguous copies or unavailable roots are intentionally not guessed. Old evidence is retained; status reports missing/new records.
- No textual diff despite new revision: inspect source_only_change, parser_changed and warnings. ZIP metadata may change without extracted text changes.

Phase 7:

- Maintenance busy: wait for writes/backup to finish or stop watch before retrying. Existing data are retained; do not remove the lock file while active.
- Backup incomplete or checksums differ: keep the suspect backup for diagnosis and use a different verified one. Never clear .incomplete to force acceptance.
- Existing AGENTS.md kept: setup --codex will not replace it. Merge manuscript instructions and restart the Codex conversation.
- Login watching did not start: no service is installed by startup generation alone. Inspect the optional installation instructions, paths and permissions; use foreground watch for diagnostics.
