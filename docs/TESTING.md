# Test strategy and executed validation

Phase 0 checked the environment and document consistency. Phases 1–4 have executable tests; see PHASE_REPORTS/PHASE_4.md for current actual results. The remaining test strategy below includes future phases.

Phase 1: clean project-local environment install, CLI help and doctor, setup from an unrelated working directory, explicit/ancestor configuration discovery, relative-path resolution, multiple source folders, unset sources, existing-config preservation, invalid configuration, smoke tests, lint and privacy exclusions. Do not require private files.

Phase 2: synthetic OOXML fixtures with expected ordered text and note links; headings, footnotes and endnotes with colliding numeric IDs and repeated markers, English/German Unicode (umlauts and ß), images/alt text/captions and caption fields, empty paragraphs, tables and unsupported features; golden JSON/Markdown with controlled metadata; malformed ZIP/XML and archive limits; unchanged source hash. Author compares an explicitly authorized real chapter copy against Word.

Phase 3: same term across chapters/notes, exact locator retrieval, English/German word retrieval and documented diacritic behavior, unchanged ingestion, changed hashes, corrupt-source retention, atomic rollback and missing files.

Phase 4: rapid saves, temporary files, replacement saves, unstable ZIPs, renames, unavailable sync files, missed events and restart reconciliation; retained revisions and correct stale status.

Phase 5: 15–30 human-curated questions including unanswerable cases; review quotations, revision provenance, footnote links and inference labels. At least five genuine cross-chapter questions accepted by the author.

Phases 6–7: analysis provenance/invalidation, nuanced vs false contradictions, opt-in and provider failures; realistic corpus performance, clean install, migrations, backup/restore and sustained editing trial.

Automated fidelity checks do not establish scholarly correctness. Record actual commands, results, untested cases and human acceptance separately in each phase report.

Phase 3 actual verification is recorded in PHASE_REPORTS/PHASE_3.md. tests/test_index.py covers multi-chapter/note search, stale and missing sources, failed parsing, interrupted transactions including abrupt subprocess termination, historical retrieval, idempotence/revert, private permissions, read-only operations, Unicode semantics, unknown-schema protection, duplicate names and source discovery.

## Phase 4 actual verification

79 tests pass, including 24 watcher/revision cases: native and polling replacement saves, debounce, partial ZIP retry/recovery, missed events/restarts, unavailable sources, unique and ambiguous renames, writer locking, history/diffs/reverts, schema migration backup and rollback, and read-only behavior. Clean installed CLI and real-corpus migration were checked. All 18 original hashes remained unchanged. A genuine Microsoft Word save could not be completed through AppleScript; Word-specific live-save acceptance remains unverified. See PHASE_REPORTS/PHASE_4.md for evidence and limitations.

## Phase 5 query workflow

The existing 79 tests remain the executable retrieval/watch regression suite. scripts/audit_query_evidence.py additionally checked 15 real-corpus term queries and 63 revision-pinned records, surrounding blocks and note anchors, a zero-hit probe, and unchanged database bytes. This does not score scholarly interpretation. See QUERY_BENCHMARK.md and PHASE_REPORTS/PHASE_5.md for the pending human-curation and author-acceptance gate.

## Phase 6 analysis

96 tests pass after adding provenance/import rejection, exact quote checks, immutable snapshots, private permissions, read-only operations, stale/missing-source detection before and after ingestion, historical dependency guards, review-history retention, no-finding records, CLI errors, unknown-schema preservation, and impact candidate cases for clear date conflict, nuanced scope and unrelated change. Synthetic assessed reports and a real conclusion summary were reviewed by the assistant; author acceptance remains pending. See PHASE_REPORTS/PHASE_6.md.

## Phase 7 validation

112 tests pass. New coverage includes backup/restore with analyses/review decisions, corrupt active-index recovery, damaged/incomplete/unsafe manifests, output preservation, source overlap, writer exclusion while readers continue, failed-output cleanup, generated Codex setup, startup-file validation, schema-1 recovery/migration and mismatched analysis dependencies. Real-corpus verification, clean installation and two accelerated 40-save trials are recorded in PHASE_REPORTS/PHASE_7.md. Multi-day author and actual login-start acceptance remain pending.
