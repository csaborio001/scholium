# Watching saves and comparing revisions — Phase 4

## Start and stop

From your configured book workspace:

```sh
scholium watch
```

Keep this terminal running while editing in Word. Restart watch after editing scholium.toml; configuration is read at startup. Ctrl-C stops the watcher and releases its lock. Closing the terminal stops this foreground process; it is not a daemon or startup service. No launchd service is installed.

Defaults: 1 second debounce/stable-file interval, periodic full source-hash reconciliation every 30 seconds, up to 3 attempts per unchanged failed file fingerprint with 1/2-second backoff. Events are hints: startup and periodic scans also find edits made while the watcher was stopped or events were missed.

```sh
scholium watch --interval 10 --settle 1 --retries 3
scholium watch --poll --interval 5
scholium watch --duration 10 --json
```

`--poll` disables native filesystem notifications but keeps periodic reconciliation. `--duration` stops after the specified seconds, useful for diagnostics. `--json` emits newline-delimited JSON events (not one giant JSON array). A pending save may still need processing when a short duration ends; the final freshness report makes this visible.

Native watchdog notifications handle file create/modify/move/delete events. Word's ~$ locks and non-DOCX temporary files are ignored; a temporary file moved onto a DOCX name triggers a check. Folder moves trigger reconciliation. Files must have unchanged hash/size/mtime/inode across the stability interval. An incomplete ZIP is retried with bounded backoff. The parser rechecks the source hash before committing. Previous successful text remains available if saves, parsing or access fail.

After the attempt limit, an unchanged failed fingerprint is not repeatedly reparsed by the same watcher. A change in its content/file signature or restarting watch permits another retry. Missing/unavailable roots are checked again periodically. If native observation cannot start, polling remains active and a warning is emitted. No sync-placeholder download or conflict resolution is attempted.

A book permits one watcher at a time using an OS-held `.scholium/watch.lock`. The file may remain after exit; the kernel lock is released automatically even after a crash. Do not delete it while a watcher is running. Manual ingest may run separately; SQLite serializes writers.

## Reconcile manually

```sh
scholium ingest --all
scholium status
```

A full ingest now also checks conservative rename matches. Missing/deleted files never erase successful revisions. Read-only status/retrieval continues to hash sources even while watch runs; it does not rely on watcher activity as proof of freshness.

## Rename and sync-conflict policy

A rename can preserve the document UUID, chapter key and revision history only when an absent old path and one previously unknown new file uniquely match the last successful source hash, the old parent and source roots are available, and no existing document has the same hash. The change is recorded as a `renamed` event. Chapter keys do not change just because a filename changes.

Ambiguous copies, changed-content renames, missing/unavailable roots and duplicate-content conflicts are not merged automatically. They remain separate/new or missing records with explicit status. This conservative policy may need a future explicit reassociation operation; it never discards old evidence.

Historical `source_path` describes the path when a revision was extracted. `current_source_path` describes the currently associated file. Old canonical snapshots are not rewritten to pretend they originated at the new path.

## List and compare

```sh
scholium revisions --chapter "CH01"
scholium diff --chapter "CH01" --from REVISION_A --to REVISION_B
```

Replace CH01 with the exact chapter key shown by status. Copy full revision IDs from `revisions`; they are not source hashes. Both endpoints must belong to that chapter. These commands are read-only and include freshness warnings.

Revision listings include source hashes, parser versions, creation times, the current pointer and transition events. Returning to earlier identical bytes reuses that revision, with a new event recording the transition. `migration_baseline` events describe the state observed during upgrade; they do not invent missing pre-upgrade event history.

Diffs compare ordered blocks and typed notes. Insert/delete/replace groups carry full before/after passages and exact revision locators. Formatting, anchors, headings and image/link metadata participate, so a strikethrough or note-body edit is visible even if ordinary body words do not change. Changes only to DOCX package bytes are distinguished from extracted-content changes. Parser changes and extraction warnings remain visible.

Alignment is best-effort: block IDs are revision-local and Word note IDs can be reassigned. A moved passage may appear as deletion plus insertion. These are structural/textual differences, not claims of a contradiction or editorial intent.

## Snapshots, upgrades and retention

Successful revisions are full canonical JSON snapshots inside SQLite, including block/note text, anchors, editorial metadata, hashes and parser versions. Every successful revision and transition event is retained indefinitely in this release; nothing is automatically pruned. Original DOCX bytes are not snapshotted by scholium. Disk use grows with successful revisions. Word originals still need independent backups.

Schema 1 upgrades to schema 2 on the first writable `ingest` or `watch`. Before any migration, SQLite's backup API creates a private `.scholium/backups/schema1-UUID.sqlite3` and checks its integrity. The additive events-table migration is transactional; original revisions and FTS records remain intact. A failed migration rolls back; retain the backup for recovery. Read-only commands never migrate and instead explain which writable command is needed. Existing unknown schema versions are still rejected.

Migration backups are retained indefinitely too. They are sensitive copies of the manuscript index. They are not a replacement for a planned, tested backup/restore workflow in the hardening phase. Stop writers before any manual restoration; do not overwrite a live database.

Exit codes: watch returns 0 on a timed/requested stop with current sources, 1 when sources remain stale/incomplete, 130 after Ctrl-C, and 2 for startup/configuration failure. In-process transient failures are emitted and retried while the loop remains active. History/diff follow retrieval codes: 0 current; 1 usable output with incomplete freshness; 2 invalid selection/index error.
