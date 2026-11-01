# Scholarly Manuscript Intelligence System

**Project brief, implementation specification, and stage-gated build plan for Codex**  
**Status:** Initial specification — implementation not yet started  
**Target:** macOS; Microsoft Word remains the author's writing environment  
**Primary use case:** A 10–20+ chapter scholarly nonfiction book in history, literary history, and the history of ideas, with in-text references and Word footnotes.

## 1. Instructions to Codex: read first

You are the lead software engineer implementing this project in a VS Code workspace. Treat this document as the governing specification, but surface ambiguities rather than guessing. **Work in phases. Do not implement the next phase until the current phase has passed automated and human acceptance checks and the user explicitly approves proceeding.** At each phase:

1. Inspect the repository and existing documentation.
2. Propose a short plan and identify decisions requiring approval.
3. Implement only the approved scope with tests and documentation.
4. Run tests, show their actual results, and describe what was not tested.
5. Provide a reproducible human acceptance checklist and demonstration commands.
6. Produce a phase completion report, including limitations and next-step recommendation.
7. Stop and request permission to continue.

Never report a test as passed unless it was run. Never modify manuscript DOCX files. Do not invent scholarly claims, quotations, citations, or source verification. Preserve manuscript privacy. Prefer simple, maintainable solutions to premature infrastructure.

## 2. Product vision and boundaries

The author edits chapters **only in Microsoft Word on a Mac**. A local Python application detects changes to chapter DOCX files, extracts text and scholarly apparatus without altering originals, maintains searchable and traceable representations, and makes the current manuscript accessible to **Codex in VS Code** through documented command-line tools. Optional later AI analysis creates chapter summaries, concept/argument maps, and change-impact reports. The author can ask questions spanning the whole book and receive evidence-backed answers pointing to chapter locations and footnotes.

### Must-have outcomes

- Word DOCX originals are the sole source of truth; no silent writes to them.
- Detect edits and reliably refresh the corresponding indexed chapter.
- Preserve headings, paragraph ordering, footnote bodies, footnote markers/anchors, and in-text citations as they appear in text.
- Search the entire current manuscript, retrieve exact passages and cite stable locations.
- Distinguish author claims, quoted or cited sources, and AI-generated interpretations.
- Show what changed between revisions and identify possible cross-chapter implications for human review.
- Support clear installation, operation, troubleshooting, backup, and recovery on macOS.
- Provide complete human-readable documentation maintained with the code.

### Not in initial scope

- Editing Word files automatically; a Word add-in; a bespoke chat GUI; cloud syncing; collaborative multiuser editing; automatic validation of cited external works; continuous background AI reasoning; model fine-tuning; or a vector database.
- AI access to external source texts unless they are separately provided and licensed/authorized.

### Operating principles

- **Retrieval, not magical permanent memory:** the database and generated files store manuscript knowledge; Codex reasons about retrieved evidence at query time. A summary is not a substitute for checking original passages.
- **Deterministic ingestion first:** extracting and indexing documents should not require AI or API calls.
- **Explicit freshness:** each answer must be grounded in the latest successfully indexed revision and show a warning if a DOCX has changed but not yet indexed.
- **Auditable outputs:** AI findings include evidence, provenance, model/time metadata, and uncertainty; they are never silently promoted to verified facts.
- **Offline by default for indexing:** optional external AI processing must be opt-in and clearly disclose manuscript data transmission and costs.

## 3. Architecture and data flow

```text
Author edits DOCX in Word (macOS)
        |
        v
Read-only source folder / safe file watcher
        |
        v
DOCX parser -> canonical structured JSON + readable Markdown
        |
        v
Validation + content hashes + revision snapshots
        |
        v
SQLite database (chapter metadata, paragraphs, notes, FTS5, revisions)
        |
        +--> CLI commands: status / ingest / search / passage / notes / diff
        |         |
        |         v
        |      Codex in VS Code -> evidence-grounded answers
        |
        +--> Optional AI analysis: summaries, claims, concepts, links,
                  change-impact reports (reviewable, versioned)
```

**Clarification:** Markdown is a human-readable derivative; SQLite is the structured search index. The Python program does **not** feed a local model continuously. Codex invokes the CLI (or, later, an optional MCP interface) to query fresh indexed material. If the manuscript is small, Codex can also read the Markdown directly, but should prefer citation-aware retrieval tools.

## 4. Proposed technology and implementation choices

- Python 3.12+ (select a supported version and pin tested dependencies).
- macOS, VS Code, Codex extension or CLI; no assumption that Codex runs as a persistent daemon.
- DOCX: read ZIP/OOXML directly for footnote fidelity, with `lxml` or standard XML tooling as appropriate. `python-docx` alone is **not** sufficient for all Word footnote relationships. Support `.docx` only initially; explain how to convert `.doc`.
- SQLite and FTS5 for keyword search; use Python's `sqlite3`.
- `watchdog` for change notifications, plus startup/manual reconciliation by file hash to catch missed events.
- `pytest` with small synthetic DOCX fixtures; logging; typed Python; `pyproject.toml`.
- Markdown + JSON outputs, with clear machine-generated headers; never edit these by hand.
- Optional AI integration later: Codex for interactive analysis; OpenAI API only if approved for unattended processing. Make provider configuration modular; do not assume that Codex usage automatically provides API access.
- Optional semantic search later only if keyword search proves inadequate in realistic tests.

### macOS specifics

Word may save by replacing a file, producing temporary `~$` files and several rapid filesystem events. Debounce events, ignore lock/temp files, wait for a stable file and valid ZIP, and retry with bounded backoff. Handle OneDrive/iCloud sync conflicts and unavailable placeholder files without deleting existing valid indexed data. Do not presume filesystem events alone guarantee freshness. Provide a foreground `watch` command before any `launchd` background service; background service setup should be optional and reversible.

## 5. Proposed repository structure

```text
scholarly-manuscript-intelligence/
  README.md
  AGENTS.md                        # concise Codex working rules
  pyproject.toml
  .gitignore
  .env.example                     # never store real credentials
  config.example.toml
  docs/
    REQUIREMENTS.md
    ARCHITECTURE.md
    DATA_MODEL.md
    USER_GUIDE.md
    DEVELOPER_GUIDE.md
    TESTING.md
    PRIVACY_AND_SECURITY.md
    TROUBLESHOOTING.md
    DECISIONS.md
    CHANGELOG.md
    PHASE_REPORTS/
  src/manuscript_intelligence/
    __init__.py
    cli.py
    config.py
    logging_config.py
    docx_reader.py
    render.py
    storage.py
    indexing.py
    watcher.py
    search.py
    revisions.py
    analysis/                    # only added in later phases
  tests/
    fixtures/                    # synthetic DOCX only
  manuscript/                    # local private originals, gitignored
  generated/                     # derived files, gitignored
  data/                          # SQLite and local snapshots, gitignored
  reports/                       # generated analyses, gitignored
```

Do not create every source module in Phase 1; this is the *target* layout. Permit an external manuscript directory via configuration. Treat all private content, generated extracts, databases, snapshots and logs as sensitive. Ensure `.gitignore` rules protect them, and document the limitations of `.gitignore` if files have already been committed.

## 6. Data model and scholarly provenance

Define and document a canonical schema before implementing the parser. At minimum:

- `Document`: unique identifier, filename, display title, file path, last observed hash, last successfully indexed hash, timestamp, indexing status, parser version.
- `Revision`: document ID, content hash, ingestion time, previous revision, optional snapshot path, extraction warnings.
- `Block`: revision ID, ordered block number, heading hierarchy, block type, full text, original OOXML anchor where feasible, paragraph ID where available.
- `Note`: revision ID, Word note ID, note type (footnote; endnote only if supported), complete note text, associated anchor(s), ordered position.
- `CitationMention`: textual occurrence in a block or note, exact span and context; **do not claim automatic bibliographic resolution unless implemented and validated**.
- `SearchRecord`: FTS5 entry linked to a specific revision/block/note.
- `Analysis`: source revision hashes, kind, content, model/provider (if applicable), generation time, confidence/uncertainty, linked evidence and human review status.

Use chapter + heading + paragraph/block locator and a short quote as a practical citation; do not promise stable printed page numbers because Word pagination varies. Distinguish stable identifiers within a revision from best-effort matching across revisions. Ensure a footnote's text remains linked to its original in-text marker. For bibliographic citations, distinguish literal in-text mentions from normalized references inferred later. Store AI-derived relationships separately from extracted manuscript facts.

## 7. CLI contract (proposed; finalize in Phase 1–4)

Use a single discoverable CLI, e.g. `manuscript`:

```bash
manuscript --help
manuscript doctor
manuscript status
manuscript ingest --all
manuscript ingest --file path/to/chapter.docx
manuscript watch
manuscript search 'Romanticism' --limit 20
manuscript passage --chapter CH03 --block 42
manuscript notes --chapter CH03
manuscript diff --chapter CH03 --from REV_A --to REV_B
manuscript export --format markdown
# Later:
manuscript analyze --chapter CH03
manuscript impact --since-last-analysis
manuscript report --latest
```

For Codex, document exact commands, output schema, error codes and safe usage in `AGENTS.md`. Prefer structured `--json` output for tool use and readable default output for humans. Ensure retrieval commands do not modify files. If `status` detects stale content, Codex should request ingestion or explain that its evidence may be outdated.

## 8. Phased delivery plan and gates

### Phase 0 — Discovery and design confirmation

**Goal:** validate environment and settle requirements before coding.

Tasks:
1. Confirm macOS version, Word version, Python installation, VS Code/Codex availability, document location (local/OneDrive/iCloud), approximate manuscript size, and whether there are tracked changes, comments, tables, images, endnotes, Zotero/EndNote fields, or multiple languages.
2. Decide how to handle tracked changes (default: do not silently conflate insertions/deletions; report unsupported cases), comments, tables, hyperlinks, fields, bibliography and endnotes. Document support matrix and known limitations.
3. Agree privacy policy and whether any manuscript may be transmitted to an AI service.
4. Draft data schema, citation locator format, and test strategy.

**Deliverables:** approved requirements, supported-feature matrix, architecture diagram, risk register, privacy decision and staged milestones.

**Gate:** user approves scope, supported Word features, and source-file location. **Do not code yet.**

### Phase 1 — Repository foundation and developer workflow

**Goal:** a reproducible, documented, testable Python application skeleton.

Tasks:
1. Create project structure, Python environment instructions, package metadata, CLI with `--help` and `doctor`, configuration example, logging, safe `.gitignore`.
2. Add pytest, formatting/linting and optional typing checks; create basic smoke tests.
3. Create all required documentation skeletons, including `AGENTS.md` for Codex.
4. Document how to run from VS Code terminal on macOS.

**Tests:** clean environment install, CLI help, `doctor`, tests and lint checks. Confirm no private content in Git.

**Gate:** all commands work on target Mac; human can follow README without developer assistance; user approves. No DOCX extraction yet.

### Phase 2 — Faithful Word extraction

**Goal:** parse a chapter into canonical JSON and readable Markdown without modifying it.

Tasks:
1. Implement OOXML DOCX reader for headings, paragraphs, text runs and footnote markers/bodies, preserving ordering and anchor relationships.
2. Define handling of tables, hyperlinks, citations/fields, tracked changes, comments, endnotes and unsupported constructs; emit warnings rather than silently dropping significant content.
3. Export deterministic structured JSON and Markdown with traceable block and note identifiers.
4. Build synthetic test documents covering multiple footnotes, repeated note markers, headings, Unicode, formatting, empty paragraphs, and edge cases.
5. Test against one *copy* of a real chapter with author permission; verify a selection of note anchors manually in Word.

**Tests:** compare extracted content to expected fixtures, verify footnote IDs and anchors, check Unicode and document ordering, prove original DOCX hash is unchanged. Record known omissions.

**Gate:** author reviews extracted chapter and footnotes against Word; no material missing/misattributed content within agreed support scope. Stop on failure.

### Phase 3 — SQLite ingestion and manuscript search

**Goal:** current cross-chapter text and notes are searchable and source-traceable.

Tasks:
1. Implement schema, migrations, revision metadata, atomic database transactions, FTS5 indexing of chapter blocks and notes.
2. Ingest all chapters; re-ingest only changed source files using content hashes.
3. Add `status`, `ingest`, `search`, `passage`, `notes`, `export` and JSON output.
4. Preserve previous good index if a new DOCX is corrupt/incomplete; surface explicit error and stale status.
5. Provide chapter-level search tests, including same term in different chapters and notes.

**Tests:** multi-chapter retrieval, correct source citations, repeat ingestion idempotence, update/reindex behavior, interrupted ingestion recovery and missing-file handling.

**Gate:** user can find several known passages and footnotes across chapters, and every returned result points to the correct source. All revisions correctly labeled.

### Phase 4 — Change detection and revision comparison

**Goal:** reliable automatic updates after Word saves, plus a clear history of changes.

Tasks:
1. Implement `watch` using debounce, stable-file checks, temp-file filtering and bounded retry.
2. Add startup and periodic/manual reconciliation using file hashes.
3. Save versioned metadata/snapshots according to a documented retention policy; add block-level or paragraph-level diffs.
4. Handle rename, delete, sync conflict, locked file and failed parse without destroying previous index.
5. Provide clear current/stale/error statuses and macOS troubleshooting; optionally add opt-in `launchd` service after foreground watch is stable.

**Tests:** save Word chapter, observe refresh; rapid saves; simulated partial DOCX; rename and restore; watcher restart; missed events; database remains valid.

**Gate:** author saves a Word chapter and can verify new content appears in search, previous revision is accessible, and failures are clearly reported. No silent loss of data.

### Phase 5 — Codex editorial query workflow

**Goal:** Codex answers manuscript-wide questions using current, cited evidence.

Tasks:
1. Document how to open workspace and ask Codex to run CLI searches and retrieve full relevant passages and notes.
2. Create reusable Codex instructions in `AGENTS.md`: check freshness, search broadly, read complete passages, verify footnote links, distinguish evidence from inference, cite exact locations, disclose uncertainty, never edit Word originals.
3. Supply example prompts: compare treatment of a concept across chapters; locate all mentions of a thinker; identify shifts in terminology; examine chronology; list potentially conflicting claims with quotations.
4. Evaluate on a human-curated benchmark of 15–30 questions with known manuscript answers and deliberately unanswerable questions.
5. Consider an MCP server only if direct CLI interaction is inadequate; do not require it initially.

**Tests:** accuracy of cited passages, no invented citations, ability to say 'not established in manuscript', and stale-index warning. Human review of interpretive conclusions.

**Gate:** author can ask at least five genuine cross-chapter questions and receive useful, accurate, source-located answers; benchmark errors documented and addressed.

### Phase 6 — Scholarly knowledge layer and editorial impact analysis

**Goal:** versioned, reviewable intellectual maps and change-impact reports.

Tasks:
1. Define structured outputs for chapter summaries, thesis/argument map, historical chronology, people, texts, movements, concepts, influences and citation mentions.
2. Distinguish verbatim claims, author interpretations, cited-source assertions and AI hypotheses. Require passage-level provenance for extracted assertions.
3. Implement optional on-demand analysis first; only later consider automatically triggered AI analysis. Ensure opt-in, costs/usage limits, privacy disclosures and provider failure handling.
4. After a revision, identify candidate related passages in other chapters using retrieval, then have AI assess *possible* implications; rank by evidence and label as suggestions, not established contradictions.
5. Generate Markdown/JSON editorial reports: changes, affected arguments, cross-chapter consistency questions, references needing review, and 'no finding' when appropriate.
6. Invalidate/recompute analyses when underlying chapter revision hashes change; never treat outdated summaries as current.
7. Add human review flags (open, accepted, dismissed) without rewriting DOCX.

**Tests:** synthetic examples of clear contradiction, nuanced interpretive difference, and unrelated change; source traceability; stale analysis detection; false-positive assessment; cost/error handling.

**Gate:** scholarly author reviews sample reports, confirms that findings are useful and evidence-based, and understands what the system cannot verify. No automatic manuscript edits.

### Phase 7 — Hardening, packaging and operational handover

**Goal:** a solid, maintainable app suitable for regular use.

Tasks:
1. Test against all chapters and realistic file sizes; benchmark extraction, search and update times.
2. Implement clear backup/restore procedures, schema migration testing, recovery from corrupt DB, and safe log retention.
3. Review security/privacy: local file permissions, secrets, generated text, Git exclusions, optional API transmissions.
4. Improve CLI ergonomics, installer/setup scripts and macOS startup options; test fresh install.
5. Run regression suite, documentation walkthrough and a sustained real-world editing trial.
6. Produce release notes, user guide, architecture guide, troubleshooting FAQ, known limitations and future roadmap.

**Tests:** clean install, backup/restore, upgrade/migration, failure recovery, privacy check, and multi-day author acceptance trial.

**Gate / Definition of Done:** all agreed critical acceptance tests pass; author can install, use, stop, recover and understand the system; no known critical data-integrity defects; user signs off release v1.0.

## 9. Cross-cutting test and quality requirements

- Unit tests for parsing, note anchors, canonical rendering, indexing, search, revision comparison and watcher event filtering.
- Integration tests using synthetic multi-chapter DOCX fixtures; never depend on a private manuscript in automated CI.
- Golden-file fixtures for deterministic JSON/Markdown output; parser/schema versions tracked.
- Failure tests: invalid ZIP, incomplete save, permission error, sync placeholder, duplicated chapter names, file removal, Unicode, large notes, unexpected OOXML constructs.
- Database transactions must be atomic; on failure, last good indexed revision stays available and is marked stale.
- All generated outputs identify source document hash/revision and generation time.
- Accessibility: readable CLI help and plain-language errors; avoid assuming software development experience.
- Manual scholarly checks must accompany automated tests; textual fidelity does not guarantee interpretive accuracy.

## 10. Documentation standard and phase reports

Maintain:

| Document | Purpose |
|---|---|
| `README.md` | What it does, quick start, current phase and limitations |
| `AGENTS.md` | Instructions for Codex to interact safely with this repository |
| `docs/REQUIREMENTS.md` | Functional requirements and support matrix |
| `docs/ARCHITECTURE.md` | System components and data flow |
| `docs/DATA_MODEL.md` | JSON, SQLite and citation locator schemas |
| `docs/USER_GUIDE.md` | Daily Word-to-Codex workflow, examples |
| `docs/DEVELOPER_GUIDE.md` | Setup, commands, maintenance and extension |
| `docs/TESTING.md` | Tests, fixtures, acceptance steps |
| `docs/PRIVACY_AND_SECURITY.md` | Local data, API opt-in, Git and backups |
| `docs/TROUBLESHOOTING.md` | macOS Word, sync, watcher, DB and CLI issues |
| `docs/DECISIONS.md` | Dated architectural decisions and tradeoffs |
| `docs/CHANGELOG.md` | Changes by phase/release |
| `docs/PHASE_REPORTS/PHASE_N.md` | Results, commands run, failures, sign-off |

Documentation must describe **actual implemented behavior**, not aspirational functionality. At each phase, update the relevant documents and explicitly mark pending features. Each phase report should contain: scope, files changed, commands/tests actually run and outcomes, manual verification steps, known risks, and approval request.

## 11. Example editorial queries to support

- “Where do I discuss the relationship between Romanticism and Enlightenment thought? Give exact passages and footnotes.”
- “Compare the meaning of ‘modernity’ in Chapters 2, 5 and 9. Are there tensions or legitimate differences in context?”
- “Where do I discuss a particular thinker’s influence on later literary movements?”
- “What claims about the chronology of this movement appear across the manuscript?”
- “What changed in Chapter 4 since the last revision, and which other chapters might be affected?”
- “Which claims cite this work? Show the actual citation text, and distinguish this from verifying the work’s contents.”
- “Are there discussions of the same concept under different terminology?”
- “What can’t you determine from the manuscript alone?”

Every substantive answer should point to manuscript locations and identify the indexed revision. For interpretive comparisons, quote minimally but sufficiently to allow checking; flag uncertainty and avoid inventing page numbers.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Footnotes lost or detached | OOXML-aware parser; anchor tests; manual comparison |
| Word save events are noisy | Debounce, stable ZIP checks, hash reconciliation |
| Stale knowledge after edit | Per-document hashes, freshness checks, analysis invalidation |
| AI fabricates citations or overstates conclusions | Retrieval-first instructions, evidence locators, review gates |
| References mistaken for verified scholarship | Separate citation mention from external source verification |
| Private text accidentally published | Git ignore, permissions, no API without explicit opt-in |
| AI cost/latency grows | Deterministic indexing, incremental updates, on-demand analysis |
| Parser loses complex Word features | Feature support matrix, explicit warnings, test fixtures |
| Data lost through failure | Atomic transactions, snapshots, backup/restore testing |
| Overengineering | CLI first, SQLite FTS5 first, defer GUI/MCP/vector search |

## 13. Immediate next action: Phase 0 only

**Paste this entire Markdown file into the new Codex workspace, then give Codex this exact instruction:**

> Read `SCHOLARLY_MANUSCRIPT_INTELLIGENCE_BUILD_PLAN.md` completely. We are starting **Phase 0 only**. Do not write application code yet. Inspect the local macOS development environment where possible; ask me for the missing information listed in Phase 0, one small group of questions at a time. Propose the final requirements, Word feature support matrix, data and citation model, privacy assumptions, and acceptance tests. Write the Phase 0 documents for my review. Stop and wait for my explicit approval before starting Phase 1. Keep all documentation readable by a non-programmer, and distinguish planned functionality from implemented functionality.

**After Phase 0 approval**, ask Codex: “Implement Phase 1 only, follow the phase gates and documentation requirements, run all tests, provide the human acceptance checklist, and stop for approval.” Repeat this pattern for each subsequent phase.

## 14. Final acceptance criteria for v1.0

The project is ready for regular use only when all of the following are demonstrated on the author's Mac:

1. A chapter can be edited and saved in Word without any intervention by the app.
2. The latest successfully indexed text and footnotes match the Word document within the agreed support scope.
3. Cross-chapter searches retrieve accurate passages with traceable chapter/block/note locators.
4. Word changes are detected or recovered by reconciliation, with transparent stale/error status.
5. Revision comparison shows what changed without corrupting or overwriting originals.
6. Codex can answer genuine manuscript-wide scholarly questions using retrieved evidence, not just old summaries.
7. AI-generated maps/reports are versioned, distinguish evidence from interpretation, and are reviewable by the author.
8. The system can be installed, operated, backed up and restored using human-readable documentation.
9. No unapproved manuscript data leaves the Mac; no credentials or manuscript contents are accidentally committed to Git.
10. Tests, manual checks, limitations, and author approval are recorded in the release report.

---

**End of specification.** This file is the starting contract for Codex, not evidence that any phase has already been implemented.
