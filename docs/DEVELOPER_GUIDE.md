# Developer guide

Use Python 3.12+; tested on Python 3.12.0, macOS arm64. From the project root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

`requirements-dev.txt` pins tested direct and transitive development dependencies. The build backend is pinned in pyproject.toml. Runtime uses the standard library plus pinned watchdog. Installation requires package downloads; installed commands require no network or credentials. No type checker is configured yet.

In VS Code open this folder, choose `.venv/bin/python` as the interpreter and open its terminal. Follow OPERATIONS.md for PATH. Entry point: scholium.cli:main. Configuration is in config.py; operational stderr logging in logging_config.py. Tests use synthetic local files only and store temporary data in `.test-tmp/`.

Never add real manuscript fixtures. Keep application artifacts under this root. Phase 2 implements bounded OOXML ZIP/XML reading in docx_reader.py and atomic-directory derivative publication in render.py. Phase 3 indexing/retrieval is implemented; Phase 4 watching/revisions are implemented; Phases 5–7 are implemented; release acceptance remains pending. No CI or background service is configured.

Extraction schema: [EXTRACTION_SCHEMA.md](EXTRACTION_SCHEMA.md). Synthetic DOCX archives are created by tests; tests/fixtures contains reviewed JSON/Markdown golden files with normalized provenance. Real chapter copies and audit outputs are private under .verify/ and never used by automated tests.

Index design and schema lifecycle: INDEX_SCHEMA.md. This release initializes schema 2, backs up and migrates schema 1 on writes, and rejects unknown versions unchanged. New migrations must be explicitly tested before release. Retrieval opens mode=ro/query_only; keep it free of implicit setup, migrations or export-file writes.

watchdog==6.0.0 is the pinned runtime dependency for filesystem hints. Polling reconciliation remains available with --poll. tests/test_watch_revisions.py exercises the engine with controlled clock values and live native/polling replacement saves; keep tests bounded and under the repository root. Schema migration tests must verify backups, rollback and read-only refusal.

Phase 7: maintenance.py verifies backup/restore artifacts. locks.py coordinates index/analysis writers with exclusive backup snapshots; readers remain read-only. integration.py generates non-overwriting book instructions and optional startup plists. scripts/install.sh installs locally without changing shell settings. Use synthetic tests for corruption/recovery; never corrupt a real index to test recovery. Current release candidate: 0.7.0; v1.0 requires a multi-day author trial and explicit sign-off.
