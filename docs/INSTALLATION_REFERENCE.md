# Installation and command reference (technical)

For everyday scholarly work, use [the user guide](USER_GUIDE.md). This reference preserves installation and command details. For current backup/recovery and setup --codex instructions, see [OPERATIONS.md](OPERATIONS.md).

**Start here to test the application:** [End-to-end test drive for Phases 1–5](TEST_DRIVE.md). It covers your configured book, an isolated Word-save test, revision comparisons, manuscript questions and optional automated checks.

## Install and add scholium to PATH on macOS

**Technical reference; current release is 0.7.0.** Setup, diagnostics, extraction, ingestion, search and revision-aware retrieval are available. Installation was checked on this Mac with Python 3.12.0.

PATH is the list of directories your terminal searches for commands. Add the directory containing the installed `scholium` executable, not the source-code folder.

### 1. Install in a project-local Python environment

To install, run:

```sh
cd /Users/csaborio/code/scholium
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
```

This keeps the Python environment and installed executable under the project directory. The expected executable is `/Users/csaborio/code/scholium/.venv/bin/scholium`.

### 2. Make the command available in new terminals

For your macOS zsh shell, open `~/.zshrc` in a text editor (create it if it does not exist) and add this line once:

```sh
export PATH="/Users/csaborio/code/scholium/.venv/bin:$PATH"
```

Save the file, then open a new Terminal window or a new VS Code integrated terminal. Alternatively, reload the settings in the current zsh terminal:

```sh
source ~/.zshrc
```

The shell settings file is outside the project because it controls your terminal globally. The app and its environment stay inside the project. These instructions do not modify your shell settings automatically.

Adding this environment to PATH also makes its Python and other installed commands available before other versions. If you prefer availability only for the current terminal, skip editing `~/.zshrc` and run the `export PATH=...` line directly instead.

### 3. Verify invocation outside the repository

After installation and PATH setup:

```sh
cd /Users/csaborio
command -v scholium
scholium --help
```

`command -v scholium` should print:

```text
/Users/csaborio/code/scholium/.venv/bin/scholium
```

When ready to configure a book, change to its chosen workspace and run `scholium setup .`. This creates `scholium.toml` there; edit its manuscript source paths before ingestion. Setup does not require the book workspace to be the application repository. Setup, standalone extraction and database ingestion are available.

## Troubleshooting PATH

- **`command not found: scholium`:** complete the installation first, check the PATH line, and open a new terminal. Adding PATH alone does not create an executable.
- **Check the installation independently of PATH:** run `/Users/csaborio/code/scholium/.venv/bin/scholium --help`. If this file is missing, installation is incomplete. This command can also be used without changing PATH.
- **A different scholium command runs:** use `type -a scholium` to inspect matches and check for shell aliases or functions that override PATH lookup.
- **The project folder moved or `.venv` was deleted:** recreate the environment, reinstall the package, and update the PATH line to the new location. Virtual environments should be recreated after moving rather than assumed portable.
- **Undo the PATH change:** remove the added line from `~/.zshrc` and open a new terminal. This does not delete the app, manuscript, or configuration.

PATH setup covers interactive zsh terminals. Future background services or other shells need their own executable-path configuration; no background service is implemented yet.

## Configure your book

```sh
scholium setup .
```

Edit the created `scholium.toml`:

```toml
schema_version = 1

[manuscript]
source_dirs = ["manuscript"]
languages = ["en", "de"]

[storage]
data_dir = ".scholium"
```

Create or select the source folders yourself. Absolute paths work too; relative paths are resolved beside the configuration file. Sources and data must be separate, non-nested folders. Setup never overwrites an existing file and creates it with owner-only permissions. It does not create or scan manuscript folders.

```sh
scholium doctor
scholium --config /absolute/path/to/scholium.toml doctor --json
```

Without `--config`, doctor looks in the current directory and then its parents, using the nearest configuration. It reports missing sources as ACTION and exits 1 until configured. It checks directory availability, not DOCX content, sync hydration or data-directory write permission. No database or logs are written by doctor.

For each book workspace, exclude `scholium.toml`, `.scholium/`, manuscript folders and any custom data folder from Git. Setup prints a reminder but does not edit your `.gitignore`. The development repository has its own exclusions; these do not protect separate book folders or files already tracked by Git.

Exit codes: 0 success; 1 doctor needs attention; 2 usage or filesystem error. JSON output uses schema_version 1. Setup reports command/ok/created/config; doctor reports command/ok/checks, each check containing name/ok/message. Usage errors are plain text on stderr even with `--json`.

## Extract one chapter (Phase 2)

From your configured book workspace:

```sh
scholium extract /absolute/path/to/chapter.docx --chapter CH01
```

The source is opened read-only. The command reports a new directory containing `chapter.json` (structured text, note links, image metadata and provenance) and `chapter.md` (readable passages, note markers, locations and warnings). The default directory is beneath configured `.scholium/extractions/`; it includes a document ID prefix, source hash and parser version.

For a separately chosen output location, or without book configuration:

```sh
scholium extract /absolute/path/to/chapter.docx --chapter CH01 --output /absolute/path/to/new-export
```

Use a **new** output directory outside the source folder. Existing directories are never intentionally replaced: for a repeat extraction choose another directory. Relative `--output` and file arguments resolve from the terminal's working directory; configured paths resolve from the config file. An explicit or discovered configuration is validated even when `--output` is supplied.

Add `--json` for a summary suitable for tools; it does not print the manuscript. Exit 0 means extraction completed, not that all Word features passed human review. Read every warning. Exit 2 means extraction failed; no new final export is published.

What to check against Word:

1. Compare headings and paragraphs, including empty paragraphs, German characters and table-cell order.
2. Check note markers such as `[endnote:1]` against full note bodies in the Notes section. These are Word's internal IDs, which may differ from displayed numbering. Repeated references must point to the same body. JSON offsets count Unicode code points in text without inserted note markers.
3. Compare caption text and saved caption numbers. Image occurrence, relationship target and available alt text are recorded; image pixels are not copied, rendered or interpreted. Floating positions and image-caption associations need manual checking.
4. Review warnings for headers/footers, list numbering, fields, comments, hidden text, unsupported diagrams/text boxes or other content. Automatic list labels are not reconstructed. A warning can mean material content is omitted; do not accept such an export without resolving that gap.

Tracked changes are rejected. Use an author-reviewed copy in Word with changes resolved; scholium never accepts or rejects changes for you. Fields retain saved results and are not refreshed. Legacy DOC, encrypted files and strict OOXML namespaces are not supported. Oversized archives/parts and XML entities are rejected. Sources over 128 MiB, parts over 32 MiB, total expanded contents over 256 MiB, or archives over 5,000 entries exceed current safety limits.

A locator combines chapter label, full revision, block ID and short exact quotation. Note IDs include their type, such as `endnote:1`. The chapter label defaults to the filename stem. Phase 2 document identity is based on the path; renaming changes it. No Word page number or permanent cross-revision paragraph ID is promised.

The extract command remains a standalone preview. Use ingest/status/search below for an indexed book. Use the foreground watcher for indexed refresh; old standalone exports do not update automatically.

### Editorial formatting

Version 0.2.1 retains direct strikethrough/highlight/bold/italic spans in JSON. Markdown marks crossed-out text with `[STRIKETHROUGH]...[/STRIKETHROUGH]`, and includes highlight colors in metadata. Crossed-out text is retained as evidence, not silently deleted or treated as current prose. Highlight colors have no inferred editorial meaning. This is separate from Track Changes, which remains unsupported. Style-inherited editorial formatting triggers a limitation warning.

The assistant can perform the acceptance comparison on an authorized private copy, including Word rendering when available, and report exceptions. You do not need to repeat routine paragraph/note comparisons already completed by the assistant.

## Index and retrieve the book (Phase 3)

Run from the folder containing scholium.toml:

```sh
scholium ingest --all
scholium status
scholium search "Weimar" --limit 5
```

Ingestion recursively finds DOCX files and skips Word lock files. Unchanged chapters are not reparsed. Each successful revision is retained; a failed update keeps the previous good one. Fix an unavailable/corrupt source in Word or select the correct source folder yourself; scholium never repairs or deletes originals. A failed file does not stop other chapters from indexing.

Search returns complete matching paragraphs or notes, with chapter/revision/locator and warnings. Copy the exact chapter key from a result or status:

```sh
scholium passage --chapter "CH01" --block 42
scholium notes --chapter "CH01" --note endnote:1
scholium export --chapter "CH01" --format markdown
```

CH01 is only an example; your default chapter keys are filename stems. Passage includes the linked notes. Use --json for automation; use --revision with passage/notes/export for a previously returned revision ID. Search normally uses the latest successfully indexed version of each document, including visibly stale evidence if a later source update failed.

Every retrieval hashes the configured sources and warns about stale, failed, new/unindexed or missing chapters. Exit 1 means attention is needed, even when results are returned. `current` is a freshness claim, not a guarantee that all Word features were extracted faithfully. Read extraction warnings separately, especially inherited editorial formatting, hidden text and unsupported content.

After Word saves, run `scholium ingest --all` again (or `ingest --file /path/to/chapter.docx`). Alternatively, leave `scholium watch` running. Search is literal keyword AND matching, case-insensitive but diacritic-sensitive; Müller and Muller differ. Full syntax, output schema and limitations: [CLI.md](CLI.md).

Exports go to stdout. If you redirect to a file, put it in your private data directory, never over an original manuscript, and keep it out of Git. The index is a rebuildable local derivative containing private text/history; it is not a backup of the Word originals.

## Automatic refresh and revision comparison

See [WATCH_AND_REVISIONS.md](WATCH_AND_REVISIONS.md) for foreground watch commands, stable-save/retry behavior, revision listings and diffs, rename policy, migration backups and retention. No startup service is installed.

## Manuscript questions (Phase 5)

Ask in this chat, for example: “How does my treatment of Goethe differ across chapters?” The assistant runs the searches and checks the supporting passages and notes. After editing in Word, say “Refresh the index and use my latest edits.” See [Asking questions about your manuscript](CODEX_WORKFLOW.md) for examples and the one-time setup for a new conversation.

## Summaries and editorial analysis (Phase 6)

Ask Codex to read a chapter and save a cited summary or concept map. After editing, ask it to compare revisions and assess possible effects elsewhere. Read saved work with `scholium analysis list`. See [ANALYSIS.md](ANALYSIS.md) for examples, review flags and how outdated analysis is identified. No background AI or API calls are used.
