# Requirements — Phase 4 implemented; automated validation complete; live Word save unverified

## Product boundaries

scholium is a macOS Python CLI; the author continues writing in Word. Indexing is local and deterministic. No GUI, Word add-in, external source verification, cloud sync, vector database, or automatic manuscript editing is planned initially.

Required outcomes: faithful extraction; footnote- and endnote-to-marker links; cross-chapter search; revision-specific citations; explicit freshness; recoverable ingestion; reviewable revision comparisons. AI interpretation is a later, separately authorized layer, never extracted fact.

Development root: `/Users/csaborio/code/scholium`. All implementation files and development artifacts stay here. The installed app must work from any working directory. A user-selected book workspace is distinct from the development repository; its editable configuration points to its manuscript sources, including external folders. No manuscript location is hard-coded.

## Setup and configuration contract — Phase 1

- `scholium setup .` creates `scholium.toml` in the current directory; `scholium setup /path/to/book` targets another directory. Installation must document adding the executable to PATH so invocation works outside the repository.
- Setup creates configuration only, without reading, copying or altering manuscripts. A missing target directory may be created; existing configuration is never overwritten. A repeated setup reports the existing file and leaves it unchanged.
- The initial file has an empty source-directory list and readable examples. The author edits it before ingestion. Setup can succeed unconfigured; doctor must clearly report that manuscript sources still need configuration.
- Absolute source paths are allowed; relative paths resolve against the configuration file's directory, never the shell's working directory. Multiple source folders are supported. Future scanning includes `.docx` recursively and ignores Word lock files; duplicates must not be indexed twice.
- Implemented discovery: an explicit global `--config /path/to/scholium.toml` takes precedence; otherwise look in the current directory and then ancestors, using the nearest configuration. Do not guess a global default book. Missing or invalid configuration produces an actionable error for commands that require it; help/setup and environment diagnostics remain available.
- Store derived data in `.scholium/` beside the configuration by default, with a configurable data directory. Source/output overlap must be rejected before ingestion. Local configuration and derived data are private; setup documentation explains Git exclusions for each book workspace.

Implemented configuration format:

```toml
schema_version = 1

[manuscript]
source_dirs = [] # e.g. ["manuscript", "/absolute/path/to/chapters"]
languages = ["en", "de"]

[storage]
data_dir = ".scholium"
```

No setup files will be created outside the development root during implementation or testing without a user-requested target.

## Word support for Phase 2

Implemented within the limitations below. Assistant-performed Word comparison completed for the selected chapter; see PHASE_REPORTS/PHASE_2.md.

| Feature | Proposed behavior |
|---|---|
| DOCX paragraphs, headings, Unicode | Preserve order and visible text; record heading hierarchy and paragraph IDs where present. |
| Footnotes | Preserve full body, Word note ID, and every marker link; exclude separator notes. Missing bodies or anchors cause validation failure. |
| In-text citations | Preserve literal text; no inferred bibliographic verification. |
| Hyperlinks | Preserve visible text and available destination; never fetch links. |
| Fields / Zotero / EndNote | Preserve saved displayed results and flag fields; do not execute, refresh, or resolve field instructions. |
| Tables | Preserve row/cell order and text, including footnote anchors; flag merged/nested layouts for review. |
| Tracked changes | Reject ingestion with a clear explanation initially; keep last successful revision. Never silently choose accepted/rejected text. |
| Comments | Warn that comment bodies are excluded; preserve manuscript body text and record comment presence. |
| Images/captions | Required: record image occurrence and available OOXML anchor/relationship and alt text; preserve ordinary caption paragraphs and saved caption field results. Do not infer image-caption associations from proximity. No OCR or interpretation of image pixels. Flag floating-image positioning and captions in unsupported containers. |
| Diagrams, equations, text boxes | No reconstruction; warn about unsupported content. Material omitted text blocks human acceptance. |
| Endnotes | Required: preserve full bodies, ordering, Word IDs and every marker link, as for footnotes. Note identity includes type so footnote 1 and endnote 1 remain distinct. |
| Headers / footers / page numbers | Exclude with explicit notice; never claim printed page locations. |
| Bibliography | Preserve ordinary displayed text; no normalization or validation of sources. |
| Languages | Required: English and German, preserving umlauts, ß, quotations and mixed-language text. Phase 3 tests exact word retrieval with an explicitly documented Unicode/diacritic policy; no promise of translation, stemming or German compound splitting. |
| Legacy DOC / encrypted DOCX | Unsupported; user converts a copy to ordinary DOCX in Word. |

Unexpected significant constructs must produce warnings or failure, not silent omissions. A warning does not prove completeness. Confirm this support scope against the actual manuscript before parser development.

## Open requirements

- Source paths are selected through setup configuration, not required for Phase 0. Storage type, corpus size and additional Word features can be assessed when a book is configured.
- Confirmed manuscript features: images/captions, endnotes, English/German. Other listed feature handling remains the proposed default.
- Manuscript passages may be used in this Codex conversation. No unattended API use is authorized.
- Human confirmation of usable Word and VS Code installations; later select a copy of a real chapter for authorized fidelity review.

## Delivery stages

0. Discovery and design: approved to proceed to Phase 1.
1. Packaging, invocation from any directory, CLI setup/help/doctor, editable configuration/discovery, safe logging, tests/lint and documentation.
2. OOXML extraction and deterministic JSON/Markdown; manual footnote review.
3. Atomic SQLite/FTS5 ingestion and revision-aware retrieval.
4. Reliable save detection, reconciliation and revision diffs.
5. Evidence-based Codex workflow and a human-curated benchmark.
6. Optional versioned AI analysis and editorial impact suggestions.
7. Performance, recovery, packaging and operational acceptance.

Each stage needs actual test evidence and human acceptance before moving on. No later stage is implemented by this design draft.

Phase 2 implementation limits: automatic list labels are warned about, not reconstructed; strict OOXML is rejected; notes inside notes are rejected; unreferenced ordinary notes fail validation. Image pixels are not exported. Paragraph runs retain text order and direct strike/highlight/bold/italic metadata; full visual formatting and style inheritance are not reconstructed. See EXTRACTION_SCHEMA.md for the implemented record format and USER_GUIDE.md for CLI usage.

Phase 3 implements SQLite ingestion, status/search/passage/notes/export and revision history retention. See CLI.md and INDEX_SCHEMA.md. Phase 4 adds watching, conservative rename recovery and diffs; AI analysis remains future work.

Phase 4 implements foreground watch, startup/periodic/manual reconciliation, bounded stable-file retries, conservative rename recovery, full revision snapshots with indefinite retention, audited transitions and block/note comparisons. launchd is optional and deferred; no background service is installed.

Phase 6 implemented in 0.6.0: explicitly imported conversation/human analysis, typed assertions and maps, dynamic revision freshness, local review history, and lexical impact candidates assessed in conversation. No unattended provider or automatic inference exists. Phase 5 workflow accepted by user; Phase 6 scholarly sample acceptance pending. Phase 7 not authorized. See ANALYSIS.md and PHASE_REPORTS/PHASE_6.md.

Phase 7 implementation is delivered in 0.7.0 with verified backup/recovery, writer coordination, installation helper, opt-in Codex setup and startup-file generation. Academic USER_GUIDE.md is separate from technical OPERATIONS.md. Multi-day real-world author acceptance and explicit v1.0 release sign-off remain pending. No startup service was installed.
