# CLI contract — 0.7.0

Global `--config FILE` precedes the command. If absent, use the nearest scholium.toml in the current directory or ancestors. JSON responses use schema_version=1. Command-local `--json` provides machine output; argparse usage errors remain plain stderr.

| Command | Purpose | Writes |
|---|---|---|
| `setup [DIRECTORY]` | Create non-overwriting configuration | Configuration only |
| `doctor` | Environment and configuration diagnostics | None |
| `extract FILE [--chapter LABEL] [--output NEW_DIRECTORY]` | Standalone Phase 2 preview | New export directory |
| `ingest --all` | Recursively index new/changed DOCX files; reconcile missing sources | Index database |
| `ingest --file FILE` | Index one configured source | Index database |
| `status` | Hash sources and report current/stale/error/missing/unavailable/unindexed/out_of_scope | None |
| `search QUERY [--limit N] [--chapter KEY]` | Search current successful blocks and notes | None |
| `passage --chapter KEY --block NUMBER_OR_ID [--revision ID]` | Full block and linked notes | None |
| `notes --chapter KEY [--note TYPE:ID] [--revision ID]` | Complete note records and anchor links | None |
| `export [--chapter KEY] [--revision ID] [--format markdown\|json]` | Read indexed derivatives to stdout | None; shell redirection writes if chosen |

Chapter keys initially use filename stems; duplicate stems receive a UUID suffix. `status --json` returns exact chapter keys, document IDs and current revision IDs. Document UUIDs also work as chapter selectors. Keys and document IDs persist for the same resolved source path. Phase 4 conservatively recovers unique identical-byte moves of missing sources; chapter keys remain stable. See WATCH_AND_REVISIONS.md.

Search uses literal Unicode word terms combined with AND; input is not executable FTS syntax. Maximum query length 2,000 characters; limit 1–100 (default 20). Results are ranked with FTS5 bm25 then deterministic chapter/type/locator ordering. The Unicode61 tokenizer is case-insensitive and diacritic-sensitive: Müller matches MÜLLER, but not Muller; ß is not automatically expanded to ss. No stemming, translation, semantic search, phrase-query syntax or compound splitting. Results may be capped by limit; a capped count is not a total match count.

`search` returns full matching records. `passage` includes full linked notes. `notes --note endnote:1` selects a typed ID. Each record contains chapter, document_id, revision, source_hash, source_path, kind, locator, citation, exact text, display_text, contains_struck_text, full canonical record and extraction_warnings. Use display_text and formatting metadata, not bare text alone, to interpret struck passages. Direct highlight/italic/bold metadata is retained. Style inheritance and other parser warnings remain material qualifications.

`freshness` accompanies every retrieval and contains checked_at, index_exists, current, documents and scan_errors. Document entries include state, observed/indexed hashes, revision and last_error where available. These checks are read-only; observations are not silently persisted. `current` means hashes/parser match at the check time, not that scholarly or visual fidelity has been certified. A foreground watcher is available, but retrieval still checks sources independently. A source can change after any completed check.

Old successful evidence remains retrievable after failures or deletion, with freshness warnings. Search selects only each document's current successful revision; explicit historical retrieval uses --revision and must be scoped to a chapter. Retain revision IDs from prior results for historical access. A selected historical revision is separately labeled even if current sources are up to date. Out-of-scope sources retain evidence with warnings; no implicit purge occurs.

Exit codes:

- 0: operation succeeded and, for retrieval/status, source freshness checks are current.
- 1: ingestion has partial failures/scan or missing-source issues; or retrieval/status found stale/incomplete evidence. Retrieval still returns useful evidence. An empty search with current evidence is success.
- 2: invalid configuration, unavailable/unsupported index, bad arguments, extraction or filesystem/database failure.

JSON `ok` indicates successful retrieval execution, while freshness.current describes evidence freshness. Thus retrieval can return ok=true and exit 1. Ingest/status ok reflects their overall result. Extraction warnings do not themselves change freshness or exit codes.

The JSON export envelope includes canonical documents and freshness. Markdown exports include freshness warnings and source/revision headers. They do not re-read DOCX content for extraction; hash checks only determine whether indexed text is current. No output file is created unless the caller redirects stdout.

Phase 4 commands:

- `watch [--settle SECONDS] [--interval SECONDS] [--retries N] [--duration SECONDS] [--poll] [--json]`: foreground writer. JSON is one event per line; Ctrl-C returns 130. It initializes/migrates the index, then performs startup/event/periodic reconciliation and stable-file ingestion.
- `revisions --chapter KEY [--json]`: read-only revision metadata plus recorded transition/rename events and current pointer.
- `diff --chapter KEY --from REVISION --to REVISION [--json]`: read-only before/after block and note groups, source/parser metadata, extraction warnings and freshness. Both revision IDs must belong to the selected chapter.

Indexed retrieval adds current_source_path; source_path remains the immutable extraction-time path. Ingest adds a renames array. Watch event types include started/status/retry/ingest/renamed/warning/error/stopped. Every event carries schema_version, command, event and UTC time. Payloads contain operational metadata and warnings, not manuscript passages. See WATCH_AND_REVISIONS.md for limitations and retention.

Phase 6 commands: `analysis template`, `analysis import FILE`, `analysis list`, `analysis show --id ID`, `analysis review --id ID --item ITEM --state open|accepted|dismissed [--comment TEXT]`, and `impact --chapter KEY --from REV --to REV --query TERM [--query TERM] [--limit N]`. All support --json; template always emits JSON. Import/review write only analysis.sqlite3. Other operations are read-only. See [ANALYSIS.md](ANALYSIS.md) for schema, historical dependencies, review history, errors and interpretation limits.

Phase 7 commands:

- `setup DIRECTORY --codex [--json]`: retain/create scholium.toml, then retain/create book-specific AGENTS.md. Existing files and symlinks are not overwritten. JSON adds codex.path, created and message.
- `backup [--output NEW_DIRECTORY] [--json]`: verified snapshot of index, analysis if present, and configuration. Default destination is data_dir/backups/book-UUID. No DOCX originals included.
- `backup-check DIRECTORY [--json]`: read-only checksum/schema/integrity/provenance verification; requires no configuration.
- `restore DIRECTORY --output NEW_DATA_DIRECTORY [--json]`: validate and recover to a separate directory; active configuration/data are unchanged.
- `startup --output NEW_PLIST [--json]`: generate a macOS user-session startup file only; installed=false. Never loads launchd automatically.

Maintenance commands return 0 on success, 2 on input/integrity/access/locking failure. Interrupted output marked .incomplete is not a usable backup. See OPERATIONS.md for safe activation, coverage and retention. Backup and writers coordinate through an OS-held .maintenance.lock; do not delete it while active.
