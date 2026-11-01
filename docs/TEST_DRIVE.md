# Test everything implemented so far

This is the user-facing test drive for Phases 1–5. Allow about 15–20 minutes. The current application version is 0.7.0; the steps below cover the original Phases 1–5 test drive, with Phase 6 checks at the end. Automated regression checks are listed at the end.

## 1. Check installation and your configured book

Open a new terminal:

```sh
command -v scholium
scholium --version
cd /Users/csaborio/code/scholium-tests
scholium doctor
scholium status
```

Expected: executable under `/Users/csaborio/code/scholium/.venv/bin`, version 0.7.0, and successful environment/configuration checks. At the last verification, your book had **17 current documents**. The intentionally removed invalid Contents.docx no longer produces a warning. Counts may change after your edits.

`doctor` checks configuration and environment; `status` checks indexed source freshness. Exit 1 with usable output means attention is needed. Exit 2 means a command/configuration/access failure. Do not join the following checks with `&&`: a freshness warning can otherwise stop the sequence.

If the command is missing, follow [PATH setup](OPERATIONS.md#install-or-upgrade-on-this-mac), or substitute `/Users/csaborio/code/scholium/.venv/bin/scholium` for `scholium`.

## 2. Test real-book ingestion, search, passages and notes

Still in your configured book folder:

```sh
scholium ingest --all
scholium search "Goethe" --limit 5
scholium search "Müller" --limit 5
scholium passage --chapter "1a-Introduction5" --block 2
scholium notes --chapter "1a-Introduction5" --note endnote:1
scholium revisions --chapter "1a-Introduction5"
```

Expected: unchanged chapters are skipped on ingestion; useful passages and notes include chapter, full revision ID and block/typed-note locators. Block 2 of the reviewed introduction retains strikethrough annotations. Notes are retrieved in full. Revision history lists stored revisions. Any new source failures should produce an explicit freshness warning. Ingestion writes only derivatives in the configured data directory, never Word originals.

You do not need to repeat the completed paragraph/endnote fidelity review. Check that the results are useful and that the command runs as documented.

## 3. Test Word saves safely in a separate book

This is the remaining live integration check: a genuine Word save reaching the index. Use a new synthetic document, not a manuscript original. These commands create a unique private test workspace under the project:

```sh
SCHOLIUM_TEST_DIR=$(mktemp -d /Users/csaborio/code/scholium/.verify/word-smoke.XXXXXX)
cd "$SCHOLIUM_TEST_DIR"
mkdir source
scholium setup .
```

Open the newly created `scholium.toml` and change only `source_dirs = []` to:

```toml
source_dirs = ["source"]
```

Keep `data_dir = ".scholium"` and the other settings. Run `pwd` to see the full workspace path. In Microsoft Word, create a new ordinary DOCX named **SaveTest.docx** in its `source` subfolder. Turn Track Changes off for this synthetic document. Type:

```text
ScholiumBeforeProbe Größe.
```

Optionally add a heading, an endnote and a caption paragraph to explore extraction. Save, then run:

```sh
scholium doctor
scholium extract source/SaveTest.docx
scholium ingest --all
scholium search "ScholiumBeforeProbe"
scholium revisions --chapter SaveTest
```

Expected: all commands succeed; extraction reports new `chapter.md` and `chapter.json` files you can open; the search returns your text and the history shows an initial revision. Save its full revision ID as **BEFORE_ID**. Standalone extraction directories are immutable; a repeated extraction of identical bytes requires a different new output directory.

### Observe stale detection and a live save

With no watcher running, change the sentence in Word to `ScholiumAfterProbe Größe.` and save. Then run:

```sh
scholium status
scholium search "ScholiumBeforeProbe"
```

Expected: SaveTest is stale, and the old indexed text remains available with a warning. Status/search do not ingest automatically.

Now start the watcher:

```sh
scholium watch --interval 2
```

Keep this terminal open. Startup reconciliation should index the saved change. In Word, change the sentence once more to `ScholiumLiveProbe Größe.` and save. Allow a few seconds for the file to settle and watch for an ingestion event. This second edit specifically exercises saving while the watcher is running.

Open a second terminal and `cd` to the full test-workspace path printed earlier. The SCHOLIUM_TEST_DIR shell variable is not automatically available in this new terminal. Run:

```sh
scholium status
scholium search "ScholiumLiveProbe"
scholium search "ScholiumBeforeProbe"
scholium revisions --chapter SaveTest
```

Expected: current status, a match for LiveProbe, no current match for BeforeProbe, and multiple retained revisions. Copy the current full revision ID as **AFTER_ID**.

Replace BEFORE_ID and AFTER_ID in these commands with the actual IDs (they are placeholders, not literal values):

```sh
scholium diff --chapter SaveTest --from BEFORE_ID --to AFTER_ID
scholium export --chapter SaveTest --revision BEFORE_ID --format markdown
```

Expected: the diff shows the changed sentence, while the explicitly historical export still contains BeforeProbe and is labeled historical. Stop the watcher with Ctrl-C in its terminal. Keep the test folder for diagnosis or remove it yourself after closing its Word document; no automatic cleanup removes evidence.

If the live save is not detected, retain the test folder and watcher output and report what happened. Do not repair or alter real manuscripts to troubleshoot this check. [Watcher details](WATCH_AND_REVISIONS.md) explain retries, polling and warnings.

## 4. Test manuscript questions in this conversation

Phase 5 works through the assistant using the existing CLI; there is no `scholium ask` command. Send, for example:

> Compare Goethe’s role in my introduction and the chapter on aestheticist narcissism.

Try a second question about namesakes:

> Do the mentions of Müller refer to the same person? Show supporting passages and avoid merging people by surname alone.

An answer should include useful evidence with exact chapter/revision/locator citations and disclose any source failures. It must not invent printed Word page numbers or claim that a limited keyword search proves book-wide absence. Your main review is whether the interpretation answers your question accurately and usefully.

The assistant has already prepared [20 private benchmark answers](../.verify/phase5/BENCHMARK_ANSWERS.md). These are examples you can inspect, not an additional mechanical checking assignment. [Workflow](CODEX_WORKFLOW.md) and [benchmark criteria](QUERY_BENCHMARK.md) explain the limits and author-acceptance status.

## 5. Optional developer regression checks

Run from the application project, not the book folder:

```sh
cd /Users/csaborio/code/scholium
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Last recorded result: **112 tests passed**, lint and formatting passed. These synthetic tests cover configuration, extraction, indexing, stale/error retention, native and polling notifications, partial/replacement saves, renames, migration backup/rollback, revision history and diffs. They do not establish scholarly correctness or replace the genuine Word-save observation above. If pytest/ruff are missing, install the project's development requirements as described in DEVELOPER_GUIDE.md.

The optional real-corpus provenance audit is described in QUERY_BENCHMARK.md. It writes private evidence, does not invoke any AI API, and is not required for this test drive.

## 6. Read the saved conclusion analysis

From your configured book workspace:

```sh
scholium analysis list
scholium analysis show --id 4f397668-820d-4452-9f55-26fba3559168
```

Expected: a current conclusion summary/map with 12 open items and exact source references. Ask Codex to explain any suggestion and record your decision only when you choose. You can also ask it to read another chapter and save a summary. After a relevant chapter changes, the old analysis should show OUTDATED; ask for a fresh analysis to retain both versions. Details: [ANALYSIS.md](ANALYSIS.md). Use a synthetic book for intentional stale-state experiments; no manuscript edit is necessary just to test a feature.

## 7. Backup and recovery trial

Ask Codex to create and verify a backup, restore it into a separate new folder, and compare saved analyses and search results without switching the active book. See OPERATIONS.md for commands. Then use the application during several ordinary writing days; accelerated tests do not replace that author trial.
