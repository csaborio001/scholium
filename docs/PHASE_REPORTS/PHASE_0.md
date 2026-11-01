# Phase 0 — discovery and design draft

Date: 2026-10-30 (Australia/Sydney). **Author answers incorporated; user authorized Phase 1 after review.**

## Scope and deliverables

Read the supplied plan completely, inspected the empty project directory and local development environment, preserved the original plan under docs/, and drafted README, requirements/support matrix, architecture, data/citation model, privacy defaults, test strategy and decisions/risk register. No application code, dependencies, source documents, environment, or Git repository was created or changed.

## Commands actually run and results

- `pwd`, `ls -la`, and repository/inherited `AGENTS.md` checks: requested root exists and was empty; no applicable AGENTS.md found in checked ancestors.
- `sw_vers`: macOS 27.2, build 26B123.
- `uname -m`: arm64.
- `command -v` for Python, uv, code, codex and git: Python 3.12 and 3.14 paths available; Codex executable present within VS Code extension; git available. `uv` and `code` absent from PATH.
- `python3 --version`: Python 3.12.0.
- App bundle version reads using PlistBuddy: Microsoft Word 16.114.3; Visual Studio Code 1.143.1.
- Python 3.12 in-memory SQLite/FTS5 and venv import probe: SQLite 3.42.0; FTS5 table creation succeeded; venv import succeeded.
- `git --version`: 2.50.1 (Apple Git-155).

Installed app metadata does not prove activation, successful app launch, or Word document behavior. No package install, parser, CLI, pytest, lint, actual manuscript fidelity check, or network/offline runtime test was performed.

## Human acceptance checklist

1. Review REQUIREMENTS.md, particularly tracked changes, endnotes, tables, fields and omitted content.
2. Review the setup/configuration contract in REQUIREMENTS.md. Source folders will be configured at setup; endnotes, images/captions and English/German are confirmed requirements.
3. Privacy choice recorded: passages allowed in this Codex conversation; no unattended API use.
4. Confirm Word and VS Code open normally on this Mac.
5. Review the revision-specific locator examples in DATA_MODEL.md.
6. Approve the design and authorize Phase 1 foundation only, or request changes.

The project has no demonstration CLI yet. Reproduce the environment check using `sw_vers`, `python3.12 --version`, and `git --version` from the project directory.

## User refinements

Incorporated `scholium setup .` and configurable source folders; required endnotes, images/captions and English/German; recorded consent for passages in this conversation only. Updated all eight design documents. No application code or manuscript processing occurred.

## Next stage

Once the open requirements are resolved and the design accepted, Phase 1 adds package metadata, installation usable from any directory, setup/help/doctor CLI, editable configuration and discovery, privacy exclusions, logging, smoke tests/lint and the remaining operational documentation. DOCX extraction remains Phase 2.

## PATH documentation follow-up

Added `docs/USER_GUIDE.md` with the planned project-local installation, zsh PATH configuration, verification from outside the repository, troubleshooting and reversal steps; linked it from README. No shell profile was changed. Installation commands remain untested until the package exists in Phase 1.
