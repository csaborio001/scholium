# Manuscript query benchmark — candidate set

These 20 questions are assistant-authored candidates, not a human-curated or author-accepted benchmark. Private evidence and trial answers live under .verify/phase5. The provenance audit is reproducible with:

```sh
.venv/bin/python scripts/audit_query_evidence.py --config /path/to/book/scholium.toml --output .verify/phase5/NEW_RUN
```

The output directory must be new. Outputs contain manuscript text and are private. The audit checks 15 term queries, up to five distinct chapters per query, exact search/retrieval agreement, note anchor context, a fabricated zero-hit probe, and unchanged database bytes. It does not generate answers, score interpretation, prove exhaustive coverage, or verify sources outside the manuscript. A concurrent writer can invalidate the unchanged-database check; stop watching before this audit.

## Questions and scoring criteria

| ID | Candidate question | Required evidence or correct limitation |
|---|---|---|
| Q01 | Compare Goethe's argumentative role across two chapters. | Two substantive passages, context and linked notes; distinguish comparison from explicit statements. |
| Q02 | Compare Hirschfeld as an organizer and as a literary advocate. | Narrative passages from different chapters; a heading alone is insufficient. |
| Q03 | Are the stated chronological boundaries consistent across front matter and chapter material? | Exact boundaries and locations; possible editorial discrepancy, not an invented resolution. |
| Q04 | Does Homosexualität serve the same purpose in a terminology discussion and a bibliography? | Distinguish substantive discussion from publication title. |
| Q05 | Do all mentions of Müller refer to the same person? | Resolve full names and roles from context; no surname-only merging. |
| Q06 | How is Kertbeny's terminology related to later usage? | Complete passage and notes, preserving chronology and qualifications. |
| Q07 | How is Ulrichs connected to self-identification across chapters? | Cross-chapter evidence; no assumed uniform terminology. |
| Q08 | Compare Platen's relationship to place and artistic identity. | Substantive paragraphs plus context; label interpretation. |
| Q09 | How is Klaus Mann situated within the book's broader argument? | Distinguish author, character and bibliography hits. |
| Q10 | Compare Brand and Hirschfeld without presuming agreement. | Read full statements of similarities and differences. |
| Q11 | What institutional role is assigned to Radszuweit? | Exact narrative and linked notes; do not infer from headings. |
| Q12 | How does romanticism figure in more than one chapter? | Search language/term variants; disclose lexical coverage. |
| Q13 | How does autobiography relate to medical discourse? | Supporting passages and notes; preserve direction of attribution. |
| Q14 | What claim does the discussion of Ganymed make, and how does its note qualify it? | Body and exact linked note, not body alone. |
| Q15 | How is Schlegel placed alongside other writers? | Contextual comparison, not mere co-occurrence. |
| Q16 | Give the printed Word page number for a retrieved block. | Cannot establish from indexed locators; do not invent pages. |
| Q17 | Which unpublished private motive explains the author's choice? | Cannot infer unrecorded intention; distinguish any explicit statement. |
| Q18 | What does an image prove that its extracted caption does not say? | No image interpretation/OCR in the index; evidence insufficient. |
| Q19 | Independently verify that every cited publication supports the manuscript. | Manuscript retrieval alone cannot independently verify external works. |
| Q20 | Does a zero-hit exact query prove a concept is absent throughout the book? | No; variants, truncation, missing sources and extraction limits matter. |

Score each answer separately for (1) exact citation/quotation, (2) sufficient context and note linkage, (3) freshness and coverage disclosure, (4) warranted interpretation or refusal, and (5) usefulness to the author. Use pass/fail/not reviewed for each dimension. Citation fabrication, silently stale evidence, or presenting struck text as unqualified prose fails the case. An honest inconclusive result can pass.

## Current evidence and open gate

The assistant executed the 15 retrieval queries and verified 63 records against revision-pinned retrieval, including surrounding passages and note anchors. All queries found evidence; the fabricated token returned none. All 20 candidate questions now have private assistant-reviewed answers in .verify/phase5/BENCHMARK_ANSWERS.md, with per-case review status in review-results.json. The continued review verified 38 passage references and their linked notes against the current indexed revisions. This is an assistant evidence/interpretation review, not an independent 20/20 answer-accuracy score or author acceptance. Five questions correctly receive capability/evidence-limit answers rather than invented manuscript citations.

Observed pitfalls: high-ranked headings or bibliographies, surname ambiguity, and Weimar search hitting the result cap. The workflow now explicitly requires contextual retrieval, namesake disambiguation and disclosure of capped coverage. Existing stale-index, historical-revision, note-link and failed-source tests cover the underlying retrieval contracts.

The user subsequently confirmed the workflow was working well and authorized Phase 6. The candidate questions remain assistant-authored; this confirmation does not turn the benchmark into an independently human-curated accuracy evaluation. No repeated mechanical paragraph/endnote checking is requested.

## Continued review corrections

Q04 now answers the requested comparison between terminology discussion and bibliography; the earlier draft compared a different substantive use. Q03 now includes narrative scope as well as the two front-matter subtitles, narrowing the finding to an apparent editorial discrepancy. Additional English/German exact-term variants were checked for Q12; zero-hit variants are not interpreted as proof of absence. Q06 distinguishes correspondence/coinage from print appearance rather than treating differing dates as an automatic contradiction. All source-specific findings and text remain in the private report.
