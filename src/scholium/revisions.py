"""Read-only revision history/diffs and conservative, auditable rename recovery."""

from collections import defaultdict
from difflib import SequenceMatcher
import json
from pathlib import Path

from .docx_reader import source_hash
from .indexing import freshness, in_sources, now, scan
from .search import document_for, freshness_message, record_result
from .storage import IndexError, connect


def recover_renames(config) -> list[dict]:
    """Only unique identical-byte moves with absent old paths are inferred."""
    files, scan_errors = scan(config)
    if scan_errors:
        return []  # Unavailable roots are not evidence of a rename.
    recovered = []
    with connect(config.data_dir, writable=True) as db:
        with db:
            db.execute("BEGIN IMMEDIATE")
            known = db.execute("""SELECT d.*,r.source_hash FROM documents d
                LEFT JOIN revisions r ON r.id=d.current_revision""").fetchall()
            known_paths = {row["path"] for row in known}
            missing, new, existing = defaultdict(list), defaultdict(list), set()
            for row in known:
                old = Path(row["path"])
                if old.exists():
                    existing.add(row["source_hash"])
                elif row["source_hash"] and in_sources(old, config):
                    missing[row["source_hash"]].append(row)
            for file in files:
                if str(file) not in known_paths:
                    try:
                        new[source_hash(file)].append(file)
                    except OSError:
                        continue
            for digest, candidates in new.items():
                if len(candidates) != 1 or len(missing[digest]) != 1 or digest in existing:
                    continue
                row, target = missing[digest][0], candidates[0]
                old = Path(row["path"])
                if old.exists() or not old.parent.is_dir() or source_hash(target) != digest:
                    continue
                db.execute(
                    "UPDATE documents SET path=?,error=NULL WHERE id=?", (str(target), row["id"])
                )
                db.execute(
                    """INSERT INTO events(document_id,happened_at,kind,from_revision,to_revision,old_path,new_path)
                    VALUES(?,?,'renamed',?,?,?,?)""",
                    (
                        row["id"],
                        now(),
                        row["current_revision"],
                        row["current_revision"],
                        str(old),
                        str(target),
                    ),
                )
                recovered.append(
                    dict(
                        chapter=row["chapter"],
                        document_id=row["id"],
                        old_path=str(old),
                        new_path=str(target),
                        method="unique_identical_hash",
                    )
                )
    return recovered


def history(config, chapter: str) -> dict:
    with connect(config.data_dir) as db:
        row = db.execute(
            "SELECT * FROM documents WHERE chapter=? OR id=?", (chapter, chapter)
        ).fetchone()
        if row is None:
            raise IndexError("Unknown chapter; use scholium status for exact keys.")
        revisions = [
            dict(r)
            for r in db.execute(
                """SELECT id,source_hash,parser_version,indexed_at,previous_revision
            FROM revisions WHERE document_id=? ORDER BY indexed_at,id""",
                (row["id"],),
            )
        ]
        events = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM events WHERE document_id=? ORDER BY id", (row["id"],)
            )
        ]
        return dict(
            schema_version=1,
            command="revisions",
            ok=True,
            chapter=row["chapter"],
            document_id=row["id"],
            current_revision=row["current_revision"],
            current_source_path=row["path"],
            revisions=revisions,
            events=events,
            freshness=freshness(config, db),
            retention="All successful revisions and events retained; no automatic pruning",
        )


def semantic_block(block: dict) -> dict:
    """Ignore shifting locators, not changes to text, notes or editorial marks."""
    return {
        key: (
            [{k: v for k, v in a.items() if k != "block_id"} for a in block[key]]
            if key == "anchors"
            else block.get(key)
        )
        for key in (
            "type",
            "text",
            "heading_level",
            "headings",
            "table_path",
            "anchors",
            "images",
            "hyperlinks",
            "formatting",
            "note_markers",
        )
    }


def diff(config, chapter: str, before: str, after: str) -> dict:
    with connect(config.data_dir) as db:
        old, _ = document_for(db, chapter, before)
        new, _ = document_for(db, chapter, after)
        a = [json.dumps(semantic_block(b), sort_keys=True) for b in old["blocks"]]
        b = [json.dumps(semantic_block(b), sort_keys=True) for b in new["blocks"]]
        changes = []
        for operation, i, j, k, end in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if operation == "equal":
                continue
            changes.append(
                dict(
                    operation=operation,
                    before=[record_result(old, block, "block") for block in old["blocks"][i:j]],
                    after=[record_result(new, block, "block") for block in new["blocks"][k:end]],
                    text_unchanged=[block["text"] for block in old["blocks"][i:j]]
                    == [block["text"] for block in new["blocks"][k:end]],
                )
            )
        old_notes, new_notes = ({n["id"]: n for n in doc["notes"]} for doc in (old, new))
        notes = []
        for key in sorted(old_notes.keys() | new_notes.keys()):
            left, right = old_notes.get(key), new_notes.get(key)

            def signature(note):
                if note is None:
                    return None
                return dict(
                    blocks=[semantic_block(b) for b in note["blocks"]], anchors=note["anchors"]
                )

            if signature(left) != signature(right):
                notes.append(
                    dict(
                        note_id=key,
                        operation="insert"
                        if left is None
                        else "delete"
                        if right is None
                        else "replace",
                        before=record_result(old, left, "note") if left else None,
                        after=record_result(new, right, "note") if right else None,
                    )
                )
        return dict(
            schema_version=1,
            command="diff",
            ok=True,
            chapter=old["chapter"],
            document_id=old["document_id"],
            from_revision=old["revision"],
            to_revision=new["revision"],
            from_hash=old["source"]["sha256"],
            to_hash=new["source"]["sha256"],
            parser_changed=old["parser_version"] != new["parser_version"],
            blocks=changes,
            notes=notes,
            warnings_before=old["warnings"],
            warnings_after=new["warnings"],
            source_only_change=old["source"]["sha256"] != new["source"]["sha256"]
            and not changes
            and not notes
            and old["warnings"] == new["warnings"],
            alignment="Best-effort ordered block matching; typed Word note IDs may be reassigned across revisions. No permanent paragraph identity or inferred editorial intent.",
            freshness=freshness(config, db),
        )


def readable(result: dict) -> str:
    lines = freshness_message(result["freshness"])
    if result["command"] == "revisions":
        lines += [
            f"{result['chapter']} · current {result['current_revision']}",
            f"Source: {result['current_source_path']}",
            result["retention"],
        ]
        lines += [
            f"{r['id']} · {r['indexed_at']} · SHA256 {r['source_hash']}"
            for r in result["revisions"]
        ]
        lines += [
            f"{e['kind']} · {e['happened_at']} · {e['from_revision']} -> {e['to_revision']}"
            for e in result["events"]
        ]
    else:
        lines += [
            f"{result['chapter']} · {result['from_revision']} -> {result['to_revision']}",
            result["alignment"],
        ]
        if result["source_only_change"]:
            lines.append(
                "Source bytes changed; extracted blocks, notes and warnings are unchanged."
            )
        if not result["blocks"] and not result["notes"]:
            lines.append("No extracted block or note changes.")
        for change in result["blocks"]:
            lines.append(
                f"BLOCK {change['operation']}"
                + (" (metadata/editorial change)" if change["text_unchanged"] else "")
            )
            for side in ["before", "after"]:
                for record in change[side]:
                    lines.extend([f"{side}: {record['citation']}", record["display_text"]])
        for change in result["notes"]:
            lines.append(f"NOTE {change['note_id']}: {change['operation']}")
            for side in ["before", "after"]:
                record = change[side]
                if record:
                    lines.extend([f"{side}: {record['citation']}", record["display_text"]])
        for side in ["before", "after"]:
            for warning in result[f"warnings_{side}"]:
                lines.append(f"EXTRACTION WARNING ({side}) {warning['code']}: {warning['message']}")
    return "\n".join(lines)
