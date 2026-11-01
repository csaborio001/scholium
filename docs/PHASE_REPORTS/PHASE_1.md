# Phase 1 — foundation implemented

Date: 2026-10-30 (Australia/Sydney). Implementation and automated checks complete. User reported all doctor checks passing with external book configuration/source folders and explicitly authorized Phase 2.

## Delivered

- Python 3.12+ package and installed `scholium` entry point, version 0.1.0.
- `setup` creates owner-only TOML configuration without overwriting existing files; accepts a target directory and leaves manuscripts untouched.
- Explicit/ancestor configuration discovery, relative source paths, multiple sources, strict configuration validation and source/data overlap rejection.
- Read-only `doctor`: Python/platform, in-memory SQLite FTS5, configuration and source-directory availability. Human-readable and versioned JSON output.
- Stderr operational logging, no file logs, no runtime third-party dependencies, private-file Git exclusions.
- Synthetic tests, pinned development tools and full setup/PATH/developer/troubleshooting documentation.

Files added: pyproject.toml, requirements-dev.txt, .gitignore, .env.example, config.example.toml, AGENTS.md, src/scholium/{__init__,cli,config,logging_config}.py, tests/test_foundation.py, docs/{USER_GUIDE,DEVELOPER_GUIDE,TROUBLESHOOTING,CHANGELOG}.md and this report. Existing design/README documents updated. Local ignored environments and verification fixtures are under .venv/, .verify/ and .test-tmp/.

## Actual validation

- `python3.12 -m venv .venv` and `.venv/bin/python -m pip install -e '.[dev]'`: succeeded.
- Independent environment `.verify/clean` and non-editable `pip install .`: wheel built and installation succeeded.
- Installed CLI `--help`: succeeded. `setup .verify/book --json`: created configuration.
- Clean-installed doctor before sources were configured: returned JSON ok=false and expected exit 1. After configuring a synthetic empty source folder: returned ok=true and exit 0.
- `.venv/bin/python -m pytest -q`: **13 passed** (final run: 0.14 seconds).
- `.venv/bin/ruff check .`: all checks passed.
- `.venv/bin/ruff format --check .`: 9 files already formatted (includes generated build copies).
- `.venv/bin/python -m pip check`: no broken requirements.
- `git check-ignore` using a disposable repository under .verify/privacy: all nine representative private paths ignored (manuscript, generated, data, reports, logs, config, .scholium, .env and .venv). No project Git repository/commits created; no private manuscript content present in the implementation.
- Clean installed package inspection: code/cache only, no manuscript assets.

Tests cover setup permissions and preservation (including an existing symlink), nearest/explicit configuration selection, path resolution, invalid schemas/types/keys and overlap, sanitized parse errors, read-only doctor and installed invocation via PATH from a different directory.

## Human acceptance

From a fresh terminal:

```sh
cd /Users/csaborio/code/scholium
export PATH="/Users/csaborio/code/scholium/.venv/bin:$PATH"
scholium --help
scholium --version
scholium setup .
```

1. Confirm help/version work and setup creates scholium.toml; repeat setup and verify it says “Kept existing”.
2. Edit manuscript.source_dirs to your actual folder(s); choose separate source and data directories. No manuscript contents will be read by doctor.
3. Run `scholium doctor`; resolve any ACTION messages. An empty source list intentionally returns exit 1.
4. Run `scholium --config /Users/csaborio/code/scholium/scholium.toml doctor --json` from another working directory and confirm the same configuration is used.
5. Follow USER_GUIDE.md to add the PATH line to ~/.zshrc if desired, open a fresh terminal, and repeat help.

## Limitations and next stage

Shell settings were not changed. User completion of persistent PATH setup and the README walkthrough is not yet verified. macOS/Python 3.12.0 was tested; other Python versions/platforms were not. No type checker or CI configured. Diagnostics do not parse files, validate sync hydration, or write-test the data directory. Source scans/deduplication, Word feature fidelity, export, search, watcher, revision handling and recovery remain future work. Installation downloads dependencies; runtime is local and contains no network operations.

Approve Phase 2 after the human checklist: faithful OOXML extraction including footnotes, endnotes, images/caption metadata and English/German text, with synthetic fidelity tests. Real chapter comparison requires an author-selected copy and manual review in Word. Phase 2 subsequently authorized; see PHASE_2.md.
