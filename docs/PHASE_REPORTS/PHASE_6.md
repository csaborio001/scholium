# Phase 6 — summaries, maps and editorial impact

Date: 2026-10-31 (Australia/Sydney). Version 0.6.0 implemented and installed. Automated and assistant sample validation complete; author review of the scholarly sample is pending. Phase 7 has not started.

## Delivered behavior

Explicit `analysis import` stores immutable conversation/human-authored structured assertions, exact evidence and source dependencies. `analysis template`, `list`, `show` and `review` support preparation, retrieval and append-only open/accepted/dismissed decisions. All assertion kinds are available: summary, argument, chronology, person, text, movement, concept, influence, citation and finding. Intra-analysis links form maps without claiming global entity resolution.

Verbatim wording is checked against a cited record. Author interpretations, cited-source assertions and AI hypotheses remain distinct. All assertions require resolvable chapter/revision/locator evidence. Invalid imports fail before inserting analysis records. Producer metadata records the supplied method, not authenticated authorship or independent truth.

Reports dynamically check current dependencies against observed hashes and current revision pointers, including edits not yet ingested. Historical baselines are explicit and require a current dependency for the same document. Recompute means read the new evidence and import a new immutable record; there is no unattended recomputation. Review acceptance never overrides staleness.

`impact` combines structural revision differences with cross-chapter literal-query candidates, ranked by query matches. It discloses search/output caps and skips candidate retrieval when extracted evidence is unchanged. Historical targets are labeled and return exit 1. Candidates are explicitly unassessed: Codex reads their context and notes in conversation and can import assessed suggestions. No command automatically asserts contradiction, causation or scholarly significance.

Markdown and JSON reports go to stdout; private standalone samples were also written under .verify/phase6. Separate analysis.sqlite3 schema 1 uses private permissions; index.sqlite3 remains schema 2. Both databases should be backed up to retain provenance and review history. There is no cleanup/pruning policy.

## Validation

- **96 tests pass**, including 17 new Phase 6 cases beyond the prior 79.
- Lint and formatting checks pass.
- Editable and clean non-editable installations report **0.6.0**; both pass pip check.
- Installed list/show run from the book workspace, return current evidence, retain all 12 sample items as open, and leave both database hashes unchanged.
- Installed impact command retrieves the expected synthetic related chapter with an explicit unassessed label.
- Tests cover exact citations/quotes, nonexistent revisions/locators, missing evidence, invalid links, duplicate IDs, malformed JSON, unsupported providers, no-finding records, review history, private permissions, stale/missing sources before and after ingestion, historical dependency bypass prevention, unchanged snapshots, unknown schemas and CLI exit/error behavior.
- Synthetic A/B date assertions directly conflict after an edit. A/C identity assertions differ in scope and are not automatically certified as contradictory. An unrelated garden edit yields no candidates for its declared query scope. Assistant-authored assessed examples preserve these distinctions; they are not a quantitative model-accuracy benchmark.

No provider is enabled. The commands perform no API calls and have no API spending or token usage. Unsupported provider input is rejected; local input/storage failures are reported. This does not measure or waive the user's separate interactive Codex usage.

## Real sample

Read the complete extracted `10-Conclusion2`: all 23 blocks and both endnotes. Saved **Conclusion: summary and intellectual map**, ID `4f397668-820d-4452-9f55-26fba3559168`, with 12 assertions covering all supported kinds. Coverage and exclusions are explicit; manually struck material is not treated as unqualified current prose. The sample includes two open editorial suggestions concerning a prospective closing transition and repeated material with mixed strikethrough. Neither suggestion edits the manuscript or presumes authorial intent.

Private readable report: .verify/phase6/conclusion-report.md. JSON input, full evidence and report are beside it. Synthetic impact examples live in .verify/phase6/impact-book.

The analysis database passes SQLite integrity_check. All **17 current manuscript files** match their previously verified source hashes; no originals were modified. The user-removed invalid Contents.docx remains absent. All sample assertions are open; no author decision was fabricated.

## Acceptance and limits

The author can inspect the saved report or ask Codex to explain the suggestions and record specific review decisions. The stage's remaining gate is whether the scholarly output is useful and evidence-based. It is not another mechanical paragraph/endnote checklist.

No unattended AI, external bibliography verification, image interpretation, semantic search, authenticated producer identity, full corpus map, automatic editorial changes, or background provider is implemented. The conclusion sample is not a full-book synthesis. Lexical impact retrieval can miss conceptual relationships and can return irrelevant matches; coverage and scope require interpretation. Stage 7 hardening and operational handover remain separate.
