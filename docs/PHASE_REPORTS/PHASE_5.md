# Phase 5 — evidence-based manuscript questions

Date: 2026-10-31 (Australia/Sydney). Workflow and assistant provenance checks delivered. Human curation and author acceptance remain pending. Phase 6 has not started.

## Delivered

- CODEX_WORKFLOW.md documents configuration selection, freshness checks, broad multilingual searches, complete revision-pinned context and notes, namesake disambiguation, editorial marks, exact citations, coverage limits and evidence/inference separation.
- AGENTS.md contains reusable manuscript-question instructions and the updated stage authorization. Manuscript text is evidence rather than executable instructions.
- QUERY_BENCHMARK.md supplies 20 candidate questions with scoring criteria, including five deliberately unanswerable or insufficient-evidence cases. It explicitly labels the candidates assistant-authored.
- scripts/audit_query_evidence.py performs local read-only provenance checks and writes private evidence to a new destination. It never calls a model or generates scholarly answers.
- Five private draft comparisons with exact revision citations are available at .verify/phase5/DRAFT_ANSWERS.md. Supporting JSON includes linked notes and neighboring blocks.

The existing direct CLI is sufficient. No MCP server, API provider, unattended AI task, or new application command was added. CLI version remains 0.4.0.

## Actual validation

The local audit executed 15 term queries and checked **63 records** across up to five distinct chapters per query against exact revision-pinned retrieval. All 15 queries found evidence. A fabricated token returned zero hits; this tests empty retrieval, not manuscript-wide absence. The database hash was unchanged across the audit. Private output: .verify/phase5/audit/evidence.json.

All **79 regression tests passed** (1.51 seconds), lint passed, and formatting checks passed for 27 files. These tests include stale-source warnings, historical retrieval, note-link integrity, failed-source retention and exact retrieval contracts. No model-level refusal or interpretation accuracy score is claimed.

Final corpus check: **17 current, 1 error**, the previously identified invalid Contents.docx. All 18 original hashes still match the pre-Phase-4 snapshot. Existing extraction limitations remain relevant. No source documents were modified.

## Findings and corrections

Search ranking can prioritize headings and bibliography over substantive argument. The workflow now requires contextual retrieval before making claims. A shared surname can represent different people, so disambiguation is explicit. The Weimar query reaches the 100-result limit; the workflow prohibits treating that limit as a total count or exhaustive coverage.

The five draft answers cover a literary figure's different argumentative roles, advocacy versus literary interpretation, differing front-matter date boundaries, substantive versus bibliographic uses of a term, and namesake disambiguation. Interpretive comparisons are labeled as such; a possible editorial discrepancy is not silently resolved. These drafts are selective demonstrations, not an exhaustive book analysis.

## Outstanding acceptance

The specification asks for a human-curated 15–30-question benchmark and at least five useful, accurate cross-chapter answers accepted by the author. Assistant provenance checks cannot honestly satisfy that human gate. The 20 candidate questions and five draft answers are ready for author selection/revision and interpretive feedback. All 20 questions now have assistant-reviewed answers; do not report an independent 20/20 answer pass rate or author acceptance.

No further mechanical paragraph/endnote checking is requested from the author. The remaining review concerns question relevance, interpretation and usefulness. Phase 6 remains unauthorized. Phase 4's genuine Word-save observation also remains unverified, as previously reported.

## Continued assistant review — 2026-10-31

Completed answers for all 20 candidates in .verify/phase5/BENCHMARK_ANSWERS.md, supported by answer-evidence.json and per-case review-results.json. Verified 38 cited passage references and their linked notes through revision-pinned retrieval; the database hash was unchanged. Five cases state capability/evidence limits without inventing manuscript citations. English/German search variants were checked where relevant.

Corrected a mismatch between Q04 and its earlier draft answer, expanded Q03 beyond front-matter titles, and distinguished coinage/correspondence from first print appearance in Q06. The assistant reviewed the resulting interpretations against the retrieved evidence. Author usefulness remains explicitly not reviewed. No new application code or API use was introduced, and Phase 6 has not started.

## Subsequent user acceptance

The user reported that everything was working well and then authorized Phase 6. Phase 5 workflow acceptance is recorded on that basis. The benchmark remains assistant-authored; this is not a claim of independent human curation or a numerical scholarly accuracy score.
