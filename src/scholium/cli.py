"""Local manuscript CLI: setup, extraction, indexing and read-only retrieval."""

import argparse
import json
import os
import platform
import sqlite3

from . import __version__
from .config import ConfigError, discover, load, setup
from .logging_config import configure
from pathlib import Path
from .docx_reader import ExtractionError, extract
from .render import publish
from .storage import IndexError
from .indexing import ingest, freshness
from .search import retrieve, readable, freshness_message
from . import revisions, watcher, analysis, maintenance, integration


def doctor(explicit: str | None) -> tuple[dict, int]:
    checks = []

    def add(name: str, ok: bool, message: str) -> None:
        checks.append({"name": name, "ok": ok, "message": message})

    add("python", True, platform.python_version())
    add("platform", True, f"{platform.system()} {platform.machine()}; macOS is the target")
    try:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
        add("fts5", True, f"SQLite {sqlite3.sqlite_version}: FTS5 available")
    except sqlite3.Error:
        add("fts5", False, "SQLite FTS5 unavailable")
    path = discover(explicit)
    if path is None:
        add("configuration", False, "No scholium.toml found. Run scholium setup .")
    else:
        try:
            config = load(path)
            add("configuration", True, str(path))
            add(
                "sources",
                bool(config.source_dirs),
                "Source folders configured"
                if config.source_dirs
                else "Edit manuscript.source_dirs in scholium.toml; no sources configured",
            )
            for source in config.source_dirs:
                add(
                    "source_directory",
                    source.is_dir() and os.access(source, os.R_OK | os.X_OK),
                    str(source),
                )
            add(
                "data_directory",
                not config.data_dir.exists() or config.data_dir.is_dir(),
                f"{config.data_dir} (not created or write-tested)",
            )
        except ConfigError as exc:
            add("configuration", False, str(exc))
    ok = all(check["ok"] for check in checks)
    return {"schema_version": 1, "command": "doctor", "ok": ok, "checks": checks}, 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    logger = configure()
    parser = argparse.ArgumentParser(description="scholium: local scholarly manuscript tools")
    parser.add_argument("--version", action="version", version=f"scholium {__version__}")
    parser.add_argument("--config", help="Explicit book configuration (before the command)")
    commands = parser.add_subparsers(dest="command", required=True)
    setup_parser = commands.add_parser(
        "setup", help="Create editable configuration; never overwrite"
    )
    setup_parser.add_argument("directory", nargs="?", default=".")
    setup_parser.add_argument("--json", action="store_true")
    setup_parser.add_argument(
        "--codex", action="store_true", help="Create book-workspace AGENTS.md without overwriting"
    )
    doctor_parser = commands.add_parser("doctor", help="Check environment and book configuration")
    doctor_parser.add_argument("--json", action="store_true")
    extract_parser = commands.add_parser(
        "extract", help="Extract one DOCX into a new JSON/Markdown directory"
    )
    extract_parser.add_argument("file")
    extract_parser.add_argument("--chapter", help="Citation label; defaults to filename stem")
    extract_parser.add_argument(
        "--output", help="New output directory; otherwise use configured data_dir"
    )
    extract_parser.add_argument(
        "--json", action="store_true", help="Print machine-readable summary, not manuscript text"
    )
    status_parser = commands.add_parser("status", help="Reconcile source hashes without writing")
    status_parser.add_argument("--json", action="store_true")
    ingest_parser = commands.add_parser("ingest", help="Atomically index new/changed chapters")
    selection = ingest_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--file")
    ingest_parser.add_argument("--json", action="store_true")
    search_parser = commands.add_parser("search", help="Search current successful revisions")
    search_parser.add_argument("query")
    search_parser.add_argument("--chapter")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--json", action="store_true")
    for command in ("passage", "notes", "export"):
        sub = commands.add_parser(command, help=f"Read indexed {command}; no source writes")
        sub.add_argument("--chapter", required=command != "export")
        sub.add_argument("--revision", help="Exact revision ID from previous retrieval")
        sub.add_argument("--json", action="store_true")
        if command == "passage":
            sub.add_argument("--block", required=True, help="Block number or b000001-style ID")
        if command == "notes":
            sub.add_argument("--note", help="Optional typed note ID, e.g. endnote:1")
        if command == "export":
            sub.add_argument("--format", choices=("markdown", "json"), default="markdown")
    watch_parser = commands.add_parser("watch", help="Foreground auto-ingestion; Ctrl-C stops")
    watch_parser.add_argument(
        "--settle", type=float, default=1.0, help="Stable-file/debounce seconds (default 1)"
    )
    watch_parser.add_argument(
        "--interval", type=float, default=30.0, help="Hash reconciliation seconds (default 30)"
    )
    watch_parser.add_argument("--retries", type=int, default=3)
    watch_parser.add_argument(
        "--duration", type=float, help="Stop after this many seconds; useful for verification"
    )
    watch_parser.add_argument(
        "--poll", action="store_true", help="Use periodic reconciliation without native events"
    )
    watch_parser.add_argument(
        "--json", action="store_true", help="Stream one JSON object per event"
    )
    history_parser = commands.add_parser(
        "revisions", help="List retained revisions and transitions"
    )
    history_parser.add_argument("--chapter", required=True)
    history_parser.add_argument("--json", action="store_true")
    diff_parser = commands.add_parser("diff", help="Compare two retained revisions without writing")
    diff_parser.add_argument("--chapter", required=True)
    diff_parser.add_argument("--from", dest="from_revision", required=True)
    diff_parser.add_argument("--to", dest="to_revision", required=True)
    diff_parser.add_argument("--json", action="store_true")
    analysis_parser = commands.add_parser(
        "analysis", help="Local revision-linked analysis; no API calls"
    )
    actions = analysis_parser.add_subparsers(dest="action", required=True)
    for action in ("template", "import", "list", "show", "review"):
        sub = actions.add_parser(action)
        sub.add_argument("--json", action="store_true")
        if action == "import":
            sub.add_argument("file", type=Path)
        if action in ("show", "review"):
            sub.add_argument("--id", required=True)
        if action == "review":
            sub.add_argument("--item", required=True)
            sub.add_argument("--state", choices=("open", "accepted", "dismissed"), required=True)
            sub.add_argument("--comment", default="")
    impact_parser = commands.add_parser(
        "impact", help="Changes and related passages for editorial review"
    )
    impact_parser.add_argument("--chapter", required=True)
    impact_parser.add_argument("--from", dest="from_revision", required=True)
    impact_parser.add_argument("--to", dest="to_revision", required=True)
    impact_parser.add_argument("--query", action="append", required=True)
    impact_parser.add_argument("--limit", type=int, default=10)
    impact_parser.add_argument("--json", action="store_true")
    for name in ("backup", "backup-check", "restore", "startup"):
        sub = commands.add_parser(
            name,
            help={
                "backup": "Save a verified private snapshot",
                "backup-check": "Verify a saved snapshot",
                "restore": "Recover a snapshot into a new data folder",
                "startup": "Generate an optional macOS startup file; do not install",
            }[name],
        )
        sub.add_argument("--json", action="store_true")
        if name in ("restore", "backup-check"):
            sub.add_argument("directory", type=Path)
        if name != "backup-check":
            sub.add_argument("--output", type=Path, required=name in ("restore", "startup"))
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            if args.config:
                parser.error("setup takes a directory, not --config")
            path, created = setup(args.directory)
            result = {
                "schema_version": 1,
                "command": "setup",
                "ok": True,
                "created": created,
                "config": str(path),
            }
            message = f"{'Created' if created else 'Kept existing'} {path}"
            message += "\nEdit manuscript.source_dirs, then run scholium doctor."
            message += "\nKeep scholium.toml and .scholium/ out of version control."
            if args.codex:
                result["codex"] = integration.codex_setup(path)
                message += "\n" + result["codex"]["message"]
            code = 0
        elif args.command in {"backup", "backup-check", "restore", "startup"}:
            if args.command == "backup-check":
                result = maintenance.verify(args.directory)
            else:
                config_path = discover(args.config)
                if config_path is None:
                    raise ConfigError("No configuration found; use --config FILE.")
                config = load(config_path)
                if args.command == "backup":
                    result = maintenance.backup(config, args.output)
                elif args.command == "restore":
                    result = maintenance.restore(config, args.directory, args.output)
                else:
                    result = integration.startup(config, args.output)
            message = f"{args.command}: {result.get('output', result.get('directory'))}"
            message += "\n" + result.get(
                "next_step",
                result.get(
                    "message",
                    "Verified index, analysis (if present) and configuration; Word originals are not included.",
                ),
            )
            code = 0
        elif args.command in {"analysis", "impact"}:
            if args.command == "analysis" and args.action == "template":
                print(json.dumps(analysis.template(), indent=2))
                return 0
            config_path = discover(args.config)
            if config_path is None:
                raise ConfigError("No configuration found; use --config FILE.")
            config = load(config_path)
            if args.command == "impact":
                result = analysis.impact(
                    config,
                    args.chapter,
                    args.from_revision,
                    args.to_revision,
                    args.query,
                    args.limit,
                )
            elif args.action == "import":
                result = analysis.import_file(config, args.file)
            elif args.action == "review":
                result = analysis.review(config, args.id, args.item, args.state, args.comment)
            else:
                result = analysis.show(config, args.id if args.action == "show" else None)
            message = analysis.readable(result)
            code = (
                0
                if result["freshness"]["current"]
                and result.get("target_is_current_revision", True)
                and all(a["current"] for a in result.get("analyses", []))
                else 1
            )
        elif args.command == "extract":
            config_path = discover(args.config)
            config = load(config_path) if config_path else None
            if not args.output and config is None:
                raise ConfigError("Use --output DIRECTORY or configure a book with scholium setup.")
            document = extract(Path(args.file), args.chapter)
            output = (
                Path(args.output).expanduser().resolve()
                if args.output
                else (
                    config.data_dir
                    / "extractions"
                    / document["document_id"][:16]
                    / (document["source"]["sha256"] + "-" + document["parser_version"])
                )
            )
            if config:
                for source in config.source_dirs:
                    if output == source or source in output.parents or output in source.parents:
                        raise ConfigError(
                            "Output and configured source directories must not overlap."
                        )
            destination = publish(document, output)
            result = dict(
                schema_version=1,
                command="extract",
                ok=True,
                output=str(destination),
                revision=document["revision"],
                blocks=len(document["blocks"]),
                notes=len(document["notes"]),
                warnings=document["warnings"],
            )
            message = f"Extracted {len(document['blocks'])} blocks and {len(document['notes'])} notes to {destination}"
            message += f"\n{len(document['warnings'])} warning(s); review chapter.json and chapter.md against Word."
            for warning in document["warnings"]:
                message += f"\nWARNING {warning['code']}: {warning['message']}"
            code = 0
        elif args.command in {"watch", "revisions", "diff"}:
            config_path = discover(args.config)
            if config_path is None:
                raise ConfigError("No configuration found; use --config FILE or scholium setup.")
            config = load(config_path)
            if args.command == "watch":

                def emit(event):
                    print(json.dumps(event) if args.json else watcher.readable(event), flush=True)

                return watcher.run(
                    config,
                    settle=args.settle,
                    interval=args.interval,
                    retries=args.retries,
                    duration=args.duration,
                    polling=args.poll,
                    emit=emit,
                )
            result = (
                revisions.history(config, args.chapter)
                if args.command == "revisions"
                else revisions.diff(config, args.chapter, args.from_revision, args.to_revision)
            )
            message = revisions.readable(result)
            code = 0 if result["freshness"]["current"] else 1
        elif args.command in {"ingest", "status", "search", "passage", "notes", "export"}:
            config_path = discover(args.config)
            if config_path is None:
                raise ConfigError(
                    "No configuration found. Run scholium setup . or pass --config FILE."
                )
            config = load(config_path)
            if args.command == "ingest":
                result = ingest(config, args.file)
                lines = [
                    f"{r['state']}: {r['chapter']}"
                    + (f" — {r['error']}" if "error" in r else f" · rev {r['revision']}")
                    for r in result["results"]
                ]
                lines.extend(
                    f"renamed: {r['chapter']} · {r['old_path']} -> {r['new_path']}"
                    for r in result.get("renames", [])
                )
                for row in result["results"]:
                    for warning in row.get("warnings", []):
                        lines.append(
                            f"WARNING {row['chapter']}: {warning['code']} — {warning['message']}"
                        )
                lines.extend(
                    f"WARNING {e['error']}: {e.get('path', '')}" for e in result["scan_errors"]
                )
                message = "\n".join(lines) or "No DOCX files found."
                code = 0 if result["ok"] else 1
            elif args.command == "status":
                state = freshness(config)
                result = dict(
                    schema_version=1, command="status", ok=state["current"], freshness=state
                )
                message = "\n".join(
                    freshness_message(state)
                    + [
                        f"{r['state']}: {r.get('chapter') or r['path']} · rev {r.get('revision')}"
                        for r in state["documents"]
                    ]
                )
                code = 0 if state["current"] else 1
            else:
                parameters = {
                    key: getattr(args, key)
                    for key in ("query", "chapter", "revision", "block", "note", "limit")
                    if hasattr(args, key)
                }
                result = retrieve(config, args.command, **parameters)
                message = readable(result)
                if args.command == "export" and args.format == "json":
                    args.json = True
                code = 0 if result["freshness"]["current"] else 1
        else:
            result, code = doctor(args.config)
            message = "\n".join(
                f"{'OK' if item['ok'] else 'ACTION'} {item['name']}: {item['message']}"
                for item in result["checks"]
            )
        print(json.dumps(result) if args.json else message)
        return code
    except (OSError, ConfigError, ExtractionError, IndexError) as exc:
        message = (
            str(exc)
            if isinstance(exc, (ConfigError, ExtractionError, IndexError))
            else "Filesystem operation failed; check paths and permissions."
        )
        if args.json:
            print(
                json.dumps(
                    {"schema_version": 1, "command": args.command, "ok": False, "error": message}
                )
            )
        else:
            logger.error(message)
        return 2
