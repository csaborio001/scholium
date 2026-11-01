# Data and citation model — draft version 0

The table below remains the target indexed data model. Phase 2 implements the standalone [extraction schema 1](EXTRACTION_SCHEMA.md); database migrations, persisted document IDs, citation detection and analysis remain future work.

| Entity | Required fields / rules |
|---|---|
| Document | Persistent UUID, unique author-facing chapter key (e.g. CH03), relative/configured path, filename, title, observed SHA-256, indexed SHA-256, observed timestamp, status, parser version. Never infer chapter identity from title alone. |
| Revision | Immutable revision ID, document UUID, exact source-byte SHA-256, parser/schema versions, UTC ingestion timestamp, prior revision ID, warnings, optional local snapshot path. |
| Block | Revision ID plus ordered block number, type, full text, heading hierarchy, OOXML part/path, optional Word paragraph ID, optional table/row/cell location. |
| Note | Revision ID plus type (footnote or endnote) and Word note ID, full ordered text, order of first occurrence; exclude Word separator notes. Footnote and endnote IDs use separate namespaces. |
| NoteAnchor | Source block (or supported note), note key, marker order and Unicode code-point offset in visible text. Supports multiple references to one note. |
| ImageOccurrence | Revision ID, containing block or available OOXML anchor, relationship/part reference, inline/floating kind and available alt text. No pixel interpretation or inferred caption link. |
| CitationMention | Block/note key, exact text span and context, detection method; no implied normalized bibliography or external verification. Deferred beyond literal text preservation. |
| SearchRecord | Revision ID and block/note key; FTS5 indexes current successful revisions by default, explicitly selected historical revisions separately. |
| Analysis | Source revision IDs/hashes, kind, output, model/provider, generation time, uncertainty, evidence links, review status; stale when any source changes. Implemented by Phase 6 as explicitly imported producer/method metadata, typed assertions and evidence; no model endpoint. |

All references must belong to the same revision unless explicitly declared cross-revision. Source-byte hashes distinguish saves; parser version distinguishes re-extraction behavior. Re-ingesting identical bytes with identical parser/schema versions is idempotent. Ordering follows document structure, not screen layout. Timestamps are UTC ISO 8601.

Proposed citation: `CH03 · rev <revision-id> · “Heading > Subheading” · block 42`, plus a short exact quotation. A note uses `CH03 · rev <revision-id> · footnote 7 (anchor: block 42)` or `CH03 · rev <revision-id> · endnote 7 (anchor: block 42)`. Full identifiers appear in JSON; abbreviated display identifiers must be unambiguous.

IDs are stable within a revision. Word paragraph IDs and content matching only assist cross-revision alignment; they do not guarantee permanent paragraph identity. Never invent Word page numbers. Distinguish source-byte changes from extracted-text changes in later diffs.

JSON exports will include schema/parser versions, document identity, source hash, revision, generation metadata, warnings, blocks, notes and anchor links. Content serialization is deterministic for fixed inputs; generation timestamps are separately identified metadata and controlled in golden tests. Markdown carries a machine-generated header and matching locators. Exact key formats and CLI JSON/error contracts are settled in their implementation phases.

Phase 3 implementation: [INDEX_SCHEMA.md](INDEX_SCHEMA.md). Persistent document UUIDs, immutable revision IDs, canonical block/note JSON and FTS records are now implemented. Literal citation detection, analysis records and rename matching remain planned.

Phase 4: schema 2 event metadata and current_source_path supplement immutable extraction provenance. Canonical revisions remain full snapshots. Transition events distinguish returning to old bytes from creation of a new revision. Diff alignment is best-effort across revision-local block/note locators; no inferred intellectual claims are added.

Phase 6: Analysis records use immutable UUIDs and contain coverage, producer, dependencies and items. Items have kind, basis, text, evidence and intra-analysis links. Evidence snapshots include exact citation, source hash and editorial metadata. Review rows append item-specific open/accepted/dismissed decisions with comments and UTC timestamps. See ANALYSIS.md for authoritative schema and historical/current dependency rules.
