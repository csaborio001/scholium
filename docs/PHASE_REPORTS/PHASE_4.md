# Phase 4 — watching and revision comparisons

Date: 2026-10-31 (Australia/Sydney). Implementation and automated validation complete. A genuine Microsoft Word save remains unverified because Word automation timed out. Phase 5 has not started.

## Delivered

Version 0.4.0 adds foreground `watch`, `revisions --chapter KEY`, and `diff --chapter KEY --from ID --to ID`. Native filesystem notifications are combined with startup and periodic hash reconciliation. Stable-file checks and bounded retries handle partial saves; unsuccessful extraction preserves the last successful evidence. Polling remains available when native observation fails. One watcher per book is enforced by an OS lock.

Unique identical-byte renames preserve document identity and record an event. Ambiguous copies and changed-content moves are not silently merged. Revision comparisons include full block/note evidence and editorial metadata, with revision-specific locators. All successful canonical snapshots and transition events are retained indefinitely; original DOCX bytes are not backed up by scholium.

Schema 2 adds transition events. Writable operations back up schema 1 before migration; read-only operations never migrate. See [operating instructions](../WATCH_AND_REVISIONS.md) for retry, rename, retention and exit-code contracts.

## Executed checks

- `.venv/bin/python -m pytest -q`: **79 passed** (final run 1.95 seconds).
- `.venv/bin/ruff check .`: passed. `.venv/bin/ruff format --check .`: 26 files formatted correctly.
- Editable and separate clean non-editable installations both report scholium 0.4.0; clean installation `pip check` reports no broken requirements.
- Installed history and diff commands ran from an unrelated directory using an explicit configuration, returned valid JSON, and left the database hash unchanged.
- Tests cover native and polling replacement-save detection, rapid saves/debounce, temporary files, partial ZIP retries/recovery, restart and missed-event reconciliation, deletion/restoration, unreadable sources, unavailable roots, conservative rename matching and ambiguity, watcher locks, native-observer startup fallback, migration backup/rollback, revision reverts and events, and block/note/formatting comparisons.
- A bounded native watcher ran against the configured real corpus and stopped normally. No watcher or startup service remains running.

## Real corpus

The configured index upgraded from schema 1 to schema 2. SQLite integrity_check returned `ok`; all 17 successful revisions remain, with 17 migration-baseline events. The schema 1 backup was independently opened and verified to contain all 17 revisions. Backup location: the configured data directory's `backups/schema1-df3e7792-7c30-4be2-a995-476bd6da0b38.sqlite3`.

Final freshness is **17 current, 1 error**. The existing 162-byte `Contents.docx` remains an invalid ZIP and is explicitly reported after bounded retries. The separate `0-Contents.docx` remains indexed. All **18 manuscript source hashes** match the pre-check snapshot. No originals were modified. Existing extraction qualifications remain applicable; freshness is not proof of complete visual fidelity.

## Word save limitation

A private synthetic document under `.verify/phase4/word-book` was used for attempted Microsoft Word save automation. AppleScript save operations timed out; the indexed synthetic file remained at its original revision. Accordingly, no genuine Word save-to-index success is claimed. Automated native filesystem and atomic replacement-save tests did pass. Word may still have the synthetic test document open; unrelated documents were not closed.

The remaining integration observation is a successful revision update after an ordinary Word save while `scholium watch` runs. No additional paragraph or endnote review is required. No long-running cloud-sync or sustained editing trial is claimed.

## Use now

From the configured book workspace, run `scholium watch` and keep that terminal open while editing. Ctrl-C stops it. `scholium revisions --chapter "1a-Introduction5"` lists stored revision IDs; pass two IDs to `scholium diff` to compare them. The known invalid Contents.docx continues to produce an incomplete-freshness warning.

Phase 5 (the evidence-based Codex workflow and question benchmark) remains separate and has not been implemented.
