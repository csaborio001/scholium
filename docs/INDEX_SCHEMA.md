# Index schema 2 — Phase 4

Current schema 2 adds an events table: integer sequence ID, document UUID, UTC happened_at, kind, from/to revision IDs, old/new paths. Events record indexed transitions (including reverts), inferred renames and migration baselines. No source text is stored in event messages.

Schema 1 -> 2 migration uses a private SQLite backup with integrity validation before a transactional table creation/baseline insertion/user_version update. It runs only from writable commands. Read-only commands refuse old schemas with an upgrade instruction. Initial databases are created directly at version 2. Unknown versions remain untouched. See WATCH_AND_REVISIONS.md for retention and recovery limits.

The following Phase 3 schema details still define the base tables; its deferred rename/migration notes are superseded by Phase 4 above.

# Index schema 1

SQLite file: configured data_dir/index.sqlite3. Application ID 1396918348; user_version=1. New indexes are initialized transactionally. Unsupported or unrecognized existing versions are rejected unchanged; this release has no prior database schema to migrate. Future upgrades must add explicit transactional migrations and preserve snapshots before incompatible changes.

Tables:

- documents: persistent UUID, unique resolved source path, unique chapter key, current successful revision pointer, last observed ingestion hash, last attempt timestamp and sanitized error.
- revisions: immutable UUID, document foreign key, source SHA-256, parser version, UTC indexed_at, previous successful revision at first creation, canonical JSON. Unique document/hash/parser combination.
- blocks: revision + block ID, number, exact text and canonical record JSON (headings, formatting, anchors, images, hyperlinks, OOXML position).
- notes: revision + typed note ID, type, Word ID, text and canonical JSON (full note paragraphs, formatting, incoming anchors and note-body markers).
- search_records: FTS5 entries keyed to document, revision, kind and block/note locator. Unicode61 tokenizer, remove_diacritics=0. Historical entries are retained; ordinary search joins the document's current revision pointer.

Source SHA-256 plus parser version identifies extraction content; UUID5 under the persisted document UUID produces a stable database revision ID. Canonical index exports use this UUID as revision, retain the Phase 2 extraction_revision separately, and replace the path-derived document ID with the persisted UUID. These additions do not change block/note content or IDs. The same bytes under another document path produce a distinct document/revision. Reverting to previously indexed bytes reuses that immutable revision and moves the current pointer; the creation chain is not a complete ingestion-event timeline.

Per-document ingestion uses BEGIN IMMEDIATE and one transaction for metadata, canonical records, FTS entries and current-pointer update. Source hashes are checked before parsing and before commit. Parsing/validation or source changes roll back the update and record an error separately; the previous current revision stays available. SQLite failures abort the command without deleting existing data. Successfully committed other chapters remain committed: corpus ingestion is deliberately incremental, not a single all-or-nothing transaction.

Foreign keys and SQLite rollback journaling are enabled. Writable connections recover hot journals after interrupted writes; read-only commands may report an index error until a writable ingest performs recovery. All read commands open mode=ro/query_only and use a consistent read transaction. They do not migrate, update observations or create a database. Disk corruption is reported, not automatically repaired.

Source discovery walks configured folders recursively, avoids symlink directories, rejects file symlinks escaping source roots, ignores Word ~$ lock files, and deduplicates resolved inode identities across overlapping roots. Same-content copies remain separate documents. Missing, inaccessible or out-of-scope documents never cause deletion. Rename resolution and retention policies belong to Phase 4.

Data directories use 0700; new index files use 0600. Canonical text and historical revisions are sensitive. No original DOCX snapshot or separate Markdown cache is created by ingestion; the canonical revision JSON stored in SQLite can regenerate exports. Schema migrations, backup/restore automation and long-term retention are future work; do not treat the index as a replacement for Word originals or backups.
