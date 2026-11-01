# Phase 2 — faithful extraction implementation

Date: 2026-10-30 (Australia/Sydney). **User-delegated Word-rendered review completed for the selected chapter. Phase 3 has not started.**

## Scope and changes

User authorized Phase 2 after a successful external-workspace doctor check and selected one real chapter for a private copy/extraction. Implemented standalone `scholium extract`, schema 1, bounded standard-library ZIP/XML reading, heading/paragraph/table order, footnotes/endnotes and marker offsets, image metadata, hyperlinks and saved field results. Unsupported significant content produces warnings or explicit failure. Exports include source hashes, parser version, UTC generation time and revision-local locators; Word files remain read-only.

New code: src/scholium/docx_reader.py and render.py. Updated cli.py, package version and pyproject.toml to 0.2.0. Added tests/test_extraction.py and synthetic golden JSON/Markdown in tests/fixtures. Updated README, AGENTS.md and operational/design documents; added EXTRACTION_SCHEMA.md before implementation and this report. Private chapter copy, extraction, audit and review notes reside under ignored `.verify/phase2/` inside the development root.

## Commands and actual results

- `.venv/bin/python -m pytest -q`: **33 passed**, final run 0.74 seconds (13 foundation + 20 extraction test cases).
- `.venv/bin/ruff check .`: all checks passed. Initial unused-import findings were fixed.
- `.venv/bin/ruff format --check .`: 14 files already formatted (includes build copies).
- `.venv/bin/python -m pip check`: no broken requirements.
- Editable installation and independent non-editable wheel installation in `.verify/clean` both updated successfully to 0.2.0. Clean-installed `--version` and synthetic extraction succeeded.
- Authorized real-copy extraction: **64 ordered blocks, 30 endnotes, 30 references**, successful JSON and Markdown publication.
- Independent private XML audit compared all body paragraphs, all endnote text and all reference IDs/offsets against the exported records. All matched. Original, private copy and export source SHA-256 matched. The initial audit comparator omitted explicit line breaks; it was corrected to account for text controls and exclude formatting properties, then passed. No manuscript content was changed.

Tests cover English/German, inherited and nested headings, empty paragraphs, run concatenation, tabs/breaks/hyphens, table order and note tables, footnote/endnote ID collision, repeated references, image/link relationships, captions/fields, literal citation text, warning paths, malformed ZIP/XML, UTF-16 DTD rejection, archive-size limits, duplicate/missing/unreferenced notes, tracked changes, source changes, private permissions, no-overwrite publication, cleanup on render failure, CLI errors and golden exports. No real manuscript is required by the automated suite.

## Real chapter findings

The selected chapter's extracted body text and endnote apparatus match the XML audit. Two warnings need human assessment:

- Headers/footers are excluded.
- Automatic list labels present in the endnote XML are not reconstructed. Word note IDs are retained and may differ from displayed numbers.

No image occurrences were found in this selected chapter. Image behavior is tested synthetically, not accepted against a real illustrated chapter. Textual XML agreement does not establish visual fidelity or scholarly correctness.

## Human acceptance checklist

Private review files (under the project root):

- `.verify/phase2/real-extraction/chapter.md`: readable extraction.
- `.verify/phase2/real-extraction/chapter.json`: structured records and provenance.
- `.verify/phase2/real-extraction/REVIEW.md`: five sampled endnote/paragraph pairs with short excerpts, for comparison in Word.
- `.verify/phase2/real-extraction/audit.json`: private audit counts/hash.

1. Open the author-selected original in Word and compare the five pairs in REVIEW.md, including full note bodies and marker positions.
2. Check paragraph order, heading text, German characters, and any meaningful formatting-dependent text.
3. Decide whether excluded headers/footers and automatic list numbering omit substantive information.
4. Report any missing or misattributed text. Do not approve fidelity if either warning hides important content.
5. If the comparison is satisfactory, accept Phase 2 and authorize Phase 3 separately. A real illustrated chapter still needs validation before claiming full manuscript coverage.

To extract another explicitly selected chapter yourself, from your configured book workspace:

```sh
scholium extract /absolute/path/to/chapter.docx --chapter CH01
```

To reproduce a separate standalone preview, choose a **new** directory outside its source folder:

```sh
scholium extract /absolute/path/to/chapter.docx --chapter CH01 --output /absolute/path/to/new-export
```

## Limits and next stage

Tracked changes, alternate embedded document content, invalid note links and strict OOXML fail explicitly. No OCR, image copying/rendering, visual layout reconstruction, field execution, external citation verification or bibliography normalization. Comments, headers/footers, equations, legacy drawings and text boxes can be excluded with warnings. Formatting is not preserved. Automatic list labels are not reconstructed. Source paths determine document identity in this standalone phase; renamed files get different IDs. Note-in-note references are unsupported.

XML/ZIP safety limits are documented in USER_GUIDE.md. Export locking coordinates scholium writers; abrupt process termination can leave a private temporary directory/lock for manual cleanup. Source hash checks guard changes during extraction, but a later Word edit naturally makes an old export historical. No watcher, database, search, stable cross-revision identity or ongoing freshness monitor exists yet.

Next recommendation after human acceptance: Phase 3 SQLite ingestion, persisted document identity, atomic current-revision indexing and citation-aware retrieval. Do not begin it until authorized.

## Assistant-performed acceptance review — 0.2.1

The user asked the assistant to perform the review instead of requiring a tedious manual checklist. Opened only the authorized private copy read-only in Microsoft Word, exported a private PDF, closed without saving the DOCX, and inspected all 20 rendered pages with native PDFKit page images. No Word connector session or LibreOffice was available; native Word automation succeeded. Original and copy hashes remain identical to the original extraction.

Found and fixed three issues:

1. The automatic-numbering warning was false for this chapter: note 23 has numId=0, explicitly disabling numbering. Regression tests cover both disabled and active numbering.
2. Eight body blocks contain manually struck text. The original plain-text representation lost that editorial distinction. Direct run strikethrough/highlight metadata is now retained; Markdown explicitly marks struck passages. It does not infer that highlighted or struck content should be deleted. Style-inherited editorial formatting is flagged as a remaining limitation.
3. Endnote 11 contains a second automatic self-marker inside its body. These markers are now preserved separately from incoming note references; a regression test verifies the repeated marker.

Compared the final extraction to Word's rendered text across all 20 pages: **48,149 normalized characters match**, including body text, endnotes, and marker numbers. Normalization removes whitespace and applies Unicode NFKC for typography; the exact verified running header/footer/page strings are excluded. Original XML comparison remains the stricter whitespace/text baseline. Native Word rendering confirms excluded page furniture consists of running titles, document/date metadata and page numbers, not substantive chapter paragraphs or note text.

Final review artifacts are private: `.verify/phase2/accepted-preview/` contains the corrected extraction; `.verify/phase2/word-review/RESULT.json` records the independent rendered comparison. Earlier outputs are retained as historical parser revisions. The previous five-note checklist is superseded by this assistant review, not an outstanding user task.

Validation after fixes: **37 tests passed**, lint passed. Golden output updated for additive metadata and deterministic sorted metadata rendering. The initially updated golden Markdown exposed a key-order mismatch; sorted-key rendering fixed it. No manuscript edits. Image-bearing real chapters and full style inheritance are still outside this selected chapter's acceptance coverage. No claim of author scholarly sign-off or Phase 3 authorization is made.
