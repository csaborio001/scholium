# Decisions and risk register

Date: 2026-10-30 (Australia/Sydney).

Confirmed by user: app name **scholium**; project root `/Users/csaborio/code/scholium`; work in stages. Repository inspection found an empty directory.

Proposed: Python package and executable both `scholium`; Python 3.12 baseline; CLI first; direct OOXML parsing; SQLite FTS5; no network indexing; revision-specific locators. User-confirmed refinements: `scholium setup .` creates editable source configuration, and the installed CLI works from anywhere. Source paths are deferred to setup. Endnotes, images/captions and English/German are required. Manuscript passages are allowed in this Codex conversation; unattended API use is not authorized. Detailed setup behavior and remaining feature exclusions are proposed for review.

Phase 0 produces design documents only. The supplied specification is reference material; its embedded sample instruction is not a separate user command. The staged design review fits the user's request to begin by stages.

| Risk | Planned mitigation / acceptance |
|---|---|
| Lost or detached notes | Validate all links; synthetic repeated-marker fixtures; author spot checks. |
| Complex Word content omitted | Explicit feature matrix, warnings/rejection and manuscript review before accepting extraction. |
| Partial saves or missed events | Stable-file checks, bounded retries, periodic source hashing. |
| Stale evidence | Report observed and indexed hashes; retain but label old evidence. |
| Private text disclosure | Local defaults, ignore rules, restricted logs and explicit AI access decision. |
| Invented scholarship | Exact evidence locators; separate literal citations from verification and interpretation. |
| Corruption or data loss | Immutable revisions, atomic transactions, later tested backup/restore. |
| Unclear chapter identity / renames | Persistent document IDs; explicit duplicate/rename policy in ingestion phase. |
| Excess scope | Complete and review one phase at a time. |

Retention durations, detailed multilingual search behavior and realistic performance targets remain open for the relevant stages. Book workspace locations are configurable; the development repository and implementation/testing artifacts remain under the user-specified project root.

Phase 2 authorized after successful external-workspace doctor check. Standalone `extract` precedes Phase 3 ingestion, using revision-local schema 1 and path-derived document IDs. Direct ZIP/XML parsing has no new runtime dependencies. Preserve saved field results, explicit note links and image metadata; reject broken note apparatus and tracked changes. User authorized one real chapter copy for fidelity checks; no broader corpus ingestion is authorized by that selection.

Phase 3 authorized with configured manuscript validation. Use per-document atomic transactions, persistent UUIDs, current-revision FTS joins, immutable canonical JSON history and mandatory read-only freshness on retrieval. Chapter labels default to filename stems to avoid guessing book order; collisions receive UUID suffixes. Literal AND searches preserve diacritics. Errors do not silently delete sources/indexed history.

Phase 4 authorized. Use watchdog 6.0.0 as hints plus periodic hashes, a foreground per-book OS lock, and three bounded attempts per unchanged failed file fingerprint. Retain all successful canonical snapshots/events; defer pruning. Schema 2 migration backs up schema 1 first. Recover only unique identical-byte missing-path renames with available roots; do not infer edited or ambiguous moves. Expose before/after block/note evidence with best-effort alignment. No launchd installation or Phase 5 work.
