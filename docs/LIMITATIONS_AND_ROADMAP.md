# Known limitations and future work

## Current boundaries

- Ordinary DOCX paragraphs, notes, captions and English/German text are supported within documented extraction limits. Tracked changes are rejected. Images are recorded as occurrences/metadata, not interpreted. Headers/footers, automatic list-label reconstruction, inherited formatting and unusual Word constructs have stated limitations. Printed page references are unavailable.
- Searches match words, not meaning. German inflections, compounds, spelling variants and translation require broader queries and reading. Results can be capped; no global absence claim follows from an empty keyword search.
- Saved analyses are authored in a conversation or by a person. Citation validation checks locations and verbatim substrings, not interpretive truth, authenticated authorship or external bibliography.
- Impact candidates are lexical leads. The assistant must assess context and scope before suggesting a change. No automatic contradiction classification or DOCX editing exists.
- Backups cover databases and configuration, not Word originals, chats, standalone exports or external report files. Recovery writes a new directory; the user deliberately switches the active configuration. Backups on the same disk do not protect against disk loss.
- All successful revisions, analyses, review decisions and backups are retained. No automatic pruning, encrypted archive, unattended remote backup, global entity resolution or semantic search is implemented.
- No background AI service or API spending is enabled. A generated macOS login-start file is optional and not automatically installed. Actual login operation has not been exercised during development.
- Benchmarks describe this Mac and the tested corpus (17 DOCX files, about 2.36 MB total). They are not guarantees for much larger documents or cloud-sync behavior.

## Before v1.0

Use the release candidate for several ordinary writing days and confirm save detection, useful evidence-based answers, revision comparisons and recovery. Automated native/polling and accelerated replacement-save tests pass, but a multi-day real Word/cloud-sync trial cannot be compressed into those checks. Record any failure and rerun the relevant checks after a fix. Final release requires explicit author sign-off; no v1.0 tag or publication has occurred.

## Possible later work, subject to authorization

- Pagination and richer search, including optional semantic retrieval with explicit privacy/cost choices.
- Reviewable reassociation of edited/ambiguous renamed chapters and a supported way to retire intentionally removed source records.
- Better formatting/list-label fidelity and optional image-aware review.
- Selective retention and backup scheduling, with clear restoration guarantees.
- More accessible report presentation and book-wide concept navigation.
- Optional provider integration only after explicit authorization, with spending limits and data-handling decisions.
