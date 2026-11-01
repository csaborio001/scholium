# Summaries, maps and editorial review

## Ask Codex to do the work

With your manuscript workspace configured, ask:

> Read the conclusion and its notes. Save a chapter summary and concept map in scholium, with supporting passages. Keep editorial suggestions open for my review.

Or, after editing a chapter:

> Compare its previous and current revisions. Find related passages in other chapters, assess possible implications, and save an editorial report. Distinguish contradictions from differences in scope.

Codex reads the evidence and produces the interpretation in your conversation. Scholium stores it locally, validates citation locations and shows when its sources have changed. It does not generate analysis by itself or run a model in the background. No API credentials or unattended provider are configured; no API requests, token usage or provider charges are incurred by these commands. Your existing interactive Codex usage is separate.

A first real sample is saved: **Conclusion: summary and intellectual map**, analysis ID `4f397668-820d-4452-9f55-26fba3559168`. It covers the complete extracted conclusion, its two notes, concepts, arguments, chronology and two open editorial suggestions. It is not a certified summary of the whole book.

## Read saved work

From the folder containing your scholium.toml:

```sh
scholium analysis list
scholium analysis show --id ANALYSIS_ID
scholium analysis show --id ANALYSIS_ID --json
```

Replace ANALYSIS_ID with an ID returned by list. Text output is Markdown; JSON is available for tooling. Both go to stdout. Redirect only to a private output file if you want a standalone report. Lists and reports show source freshness; an analysis depending on a changed, missing or unreadable source is labeled OUTDATED even before re-ingestion. A later successful ingestion also invalidates analyses of an older current dependency. Historical baselines in an impact report are explicitly labeled historical.

To update an analysis, ask Codex to reread the new revision and import a new analysis. Old analysis records remain intact; no automatic recomputation or deletion occurs. Acceptance of a finding never overrides its source freshness.

## Review suggestions

Each assertion begins as `open`. Ask Codex to accept or dismiss particular suggestions, or run:

```sh
scholium analysis review --id ANALYSIS_ID --item ITEM_ID --state accepted --comment "My review decision"
scholium analysis review --id ANALYSIS_ID --item ITEM_ID --state dismissed --comment "Different scopes; no change needed"
```

Use `--state open` to reopen. Review decisions are recorded as an append-only history, separate from the original assertion. These flags record your judgment; they do not edit DOCX or establish factual truth. Codex must not accept/dismiss findings on your behalf without your instruction.

## What is stored

Each immutable analysis contains a title, producer, method, coverage limits, chapter/revision/hash dependencies, and assertion items. Kinds: summary, argument, chronology, person, text, movement, concept, influence, citation and finding. `links` connect item IDs within that analysis into a map; describe the relationship in the assertion text. There is no inferred global entity identity or automatically resolved bibliography.

Each item has one explicit basis:

- `verbatim`: exact wording checked against a cited paragraph or note.
- `author_interpretation`: an interpretation attributed to the manuscript author.
- `cited_source_assertion`: a claim the manuscript attributes to a cited source; the external source is not independently verified.
- `ai_hypothesis`: an assistant synthesis, interpretation or suggestion requiring review.

Every item requires exact passage/note references. Scholium resolves those references into saved evidence with editorial markings and extraction warnings. It validates existence and exact verbatim substrings; it cannot certify that paraphrases or interpretations are warranted. Producer identity/method are supplied metadata, not authenticated authorship or proof that all declared context was read.

Data live in the private configured `.scholium/analysis.sqlite3`, separate from the manuscript index. No migration of the existing index is needed. Both databases contain private evidence; back up both to retain analyses and review history. Deleting/replacing the index can break provenance; do not regard the analysis database as a DOCX backup. All analyses and review decisions are retained; no pruning exists.

## Assistant/technical workflow

Get a JSON starter without writing files:

```sh
scholium analysis template
```

Fill its fields with analysis authored in the conversation, then save that JSON to a private file and import it explicitly:

```sh
scholium analysis import /absolute/path/to/private-analysis.json
```

No import happens from watch or ingest. The file must be UTF-8 JSON, at most 5 MiB, with no unknown fields. Each item requires id, kind, basis, text, evidence and links. Each evidence reference requires the canonical chapter key, full revision UUID and exact block or typed-note locator. An analysis can have zero items to record **no finding in its declared coverage**, but must still declare its source dependencies. Invalid inputs leave analysis records unchanged.

Dependencies normally have `chapter`, `revision` and optional `role: "current"`. For an impact report, declare the old revision with `role: "historical"` and the new revision with `role: "current"`. Every historically referenced document must also have a current-role dependency. Add current-role dependencies for all other chapters actually used, including context that informed a no-finding assessment. Only current-role dependencies are compared to the latest source state; historical evidence stays explicitly historical.

## Find candidate effects of a change

```sh
scholium revisions --chapter CHAPTER
scholium impact --chapter CHAPTER --from OLD_REV --to NEW_REV --query "concept" --query "person" --limit 10
```

Use actual chapter/revision IDs and terms relevant to the change. Repeat --query up to 10 times. The report contains the full structural diff, related records in other chapters, extraction warnings in JSON/diff evidence, and coverage limits. Candidates are ranked by number of distinct supplied queries matched, then citation. It searches up to 100 records per query before excluding the changed chapter. Capped searches or output limits are disclosed. A historical target revision is labeled and returns exit 1. No extracted changes means candidate retrieval is skipped. A no-candidate result is **not** proof of no implications.

This is the retrieval step, not the scholarly assessment. Codex must read each candidate's surrounding passages and notes, then assess possible effects in conversation. Save assessed implications as `finding` items with `ai_hypothesis` basis and appropriate dependencies. Put affected argument, consistency question and reference-review suggestions in separate items as useful. A suggested contradiction must have evidence on both sides and a scope comparison. Preserve nuanced differences rather than treating every shared term as a conflict. The CLI never automatically certifies a contradiction.

## Errors and limitations

Exit 0: current dependencies and overall corpus freshness. Exit 1: stale analysis or incomplete corpus; useful reports still return. An import can succeed and return 1 because its evidence is already historical/stale; the returned analysis ID confirms storage. Exit 2: invalid input, missing ID, access/storage or configuration failure. `analysis template` needs no book configuration and prints JSON even without --json.

No provider/network mode is implemented. Unsupported producer kinds (including unattended API output) are rejected. There is therefore no silent provider fallback, API spending or network retry. Local input/storage errors are reported and prior stored analyses are retained. The author must review useful examples before the next phase; automated provenance checks are not scholarly acceptance.
