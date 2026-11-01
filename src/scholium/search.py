"""Read-only, revision-aware retrieval with source freshness on every response."""

import json
import re

from .indexing import freshness
from .render import markdown
from .storage import IndexError, connect


def annotated(block: dict) -> str:
    """Use the same editorial annotations as the standalone Markdown exporter."""
    text = block["text"]
    inserts = {}
    for anchor in block.get("anchors", []):
        inserts.setdefault(anchor["offset"], []).append((1, f"[{anchor['note_id']}]"))
    for span in block.get("formatting", []):
        props = span["properties"]
        if props.get("strike") or props.get("dstrike"):
            inserts.setdefault(span["start"], []).append((2, "[STRIKETHROUGH]"))
            inserts.setdefault(span["end"], []).append((0, "[/STRIKETHROUGH]"))
    for index, marker in enumerate(block.get("note_markers", [])):
        if not (block["number"] == 1 and index == 0 and marker["offset"] == 0):
            inserts.setdefault(marker["offset"], []).append(
                (1, f"[{marker['note_id']} self-marker]")
            )
    for offset in sorted(inserts, reverse=True):
        text = (
            text[:offset]
            + "".join(v for _, v in sorted(inserts[offset], key=lambda x: x[0]))
            + text[offset:]
        )
    return text


def document_for(db, chapter: str, revision: str | None = None) -> tuple[dict, bool]:
    row = db.execute(
        "SELECT * FROM documents WHERE chapter=? OR id=?", (chapter, chapter)
    ).fetchone()
    if row is None:
        raise IndexError("Unknown chapter. Run scholium status to find its exact chapter key.")
    selected = revision or row["current_revision"]
    saved = db.execute(
        "SELECT canonical_json FROM revisions WHERE id=? AND document_id=?", (selected, row["id"])
    ).fetchone()
    if saved is None:
        raise IndexError("No successful matching revision for this chapter.")
    document = json.loads(saved[0])
    document["current_source_path"] = row["path"]
    return document, selected == row["current_revision"]


def record_result(doc: dict, record: dict, kind: str) -> dict:
    blocks = [record] if kind == "block" else record["blocks"]
    return dict(
        chapter=doc["chapter"],
        document_id=doc["document_id"],
        revision=doc["revision"],
        source_hash=doc["source"]["sha256"],
        source_path=doc["source"]["path"],
        current_source_path=doc.get("current_source_path", doc["source"]["path"]),
        kind=kind,
        locator=record["id"],
        citation=f"{doc['chapter']} · rev {doc['revision']} · {record['id']}",
        text=record["text"],
        display_text="\n".join(annotated(block) for block in blocks),
        contains_struck_text=any(
            span["properties"].get("strike") or span["properties"].get("dstrike")
            for block in blocks
            for span in block.get("formatting", [])
        ),
        record=record,
        extraction_warnings=doc["warnings"],
    )


def retrieve(
    config,
    command: str,
    *,
    query: str = "",
    chapter: str | None = None,
    revision: str | None = None,
    block: str | None = None,
    note: str | None = None,
    limit: int = 20,
) -> dict:
    with connect(config.data_dir) as db:
        state = freshness(config, db)
        result = dict(schema_version=1, command=command, ok=True, freshness=state)
        if command == "search":
            terms = re.findall(r"[^\W_]+", query, re.UNICODE)
            if not terms or len(query) > 2000 or not 1 <= limit <= 100:
                raise IndexError(
                    "Provide a nonempty search (up to 2000 characters) and a limit from 1 to 100."
                )
            # Literal AND terms; no SQL or FTS syntax is accepted from the user.
            expression = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
            params = [expression]
            sql = """SELECT s.document_id,s.revision_id,s.kind,s.locator,r.canonical_json,d.path AS current_path
                FROM search_records s JOIN documents d ON d.id=s.document_id AND d.current_revision=s.revision_id
                JOIN revisions r ON r.id=s.revision_id WHERE search_records MATCH ?"""
            if chapter:
                # Validate the chapter even when no match would otherwise hide a typo.
                document_for(db, chapter)
                sql += " AND (d.chapter=? OR d.id=?)"
                params.extend([chapter, chapter])
            sql += " ORDER BY bm25(search_records), d.chapter, s.kind, s.locator LIMIT ?"
            params.append(limit)
            matches = []
            for row in db.execute(sql, params):
                doc = json.loads(row["canonical_json"])
                doc["current_source_path"] = row["current_path"]
                records = doc["blocks"] if row["kind"] == "block" else doc["notes"]
                record = next(r for r in records if r["id"] == row["locator"])
                matches.append(record_result(doc, record, row["kind"]))
            result.update(
                query=query,
                semantics="literal AND terms; case-insensitive, diacritic-sensitive",
                results=matches,
                limit=limit,
            )
        elif command in {"passage", "notes"}:
            doc, current = document_for(db, chapter, revision)
            result.update(
                chapter=doc["chapter"], revision=doc["revision"], is_current_revision=current
            )
            if command == "passage":
                locator = f"b{int(block):06d}" if block.isdigit() else block
                record = next((b for b in doc["blocks"] if b["id"] == locator), None)
                if record is None:
                    raise IndexError("Block not found in this revision.")
                result["passage"] = record_result(doc, record, "block")
                linked = {a["note_id"] for a in record["anchors"]}
                result["linked_notes"] = [
                    record_result(doc, n, "note") for n in doc["notes"] if n["id"] in linked
                ]
            else:
                notes = [n for n in doc["notes"] if note is None or n["id"] == note]
                if note is not None and not notes:
                    raise IndexError("Note not found; use its typed ID, for example endnote:1.")
                result["notes"] = [record_result(doc, n, "note") for n in notes]
        elif command == "export":
            if revision and not chapter:
                raise IndexError("--revision requires --chapter.")
            keys = (
                [chapter]
                if chapter
                else [
                    r[0]
                    for r in db.execute(
                        "SELECT chapter FROM documents WHERE current_revision IS NOT NULL ORDER BY chapter"
                    )
                ]
            )
            result["documents"] = [document_for(db, key, revision)[0] for key in keys]
            result["historical_selection"] = bool(revision)
        return result


def freshness_message(state: dict) -> list[str]:
    lines = [
        f"Freshness checked at {state['checked_at']}: "
        + ("current" if state["current"] else "ATTENTION — evidence may be stale or incomplete")
    ]
    if not state.get("index_exists", True):
        lines.append("WARNING: no index exists; run scholium ingest --all.")
    for doc in state["documents"]:
        if doc["state"] != "current":
            lines.append(f"WARNING {doc['state']}: {doc.get('chapter') or doc['path']}")
    for error in state["scan_errors"]:
        lines.append(f"WARNING {error['error']}: {error.get('path', '')}")
    return lines


def readable(result: dict) -> str:
    lines = freshness_message(result["freshness"])
    if result.get("is_current_revision") is False or result.get("historical_selection"):
        lines.append(
            "WARNING: explicitly selected historical revision; not necessarily the current indexed text."
        )
    if result["command"] == "export":
        return "\n".join(lines) + "\n\n" + "\n\n".join(markdown(doc) for doc in result["documents"])
    records = result.get("results", result.get("notes", []))
    if "passage" in result:
        records = [result["passage"], *result["linked_notes"]]
    for record in records:
        lines.extend(["", record["citation"]])
        if record["contains_struck_text"]:
            lines.append("EDITORIAL: contains struck text; markings retained below.")
        # Full records avoid detached snippets hiding the scope of editorial markings.
        lines.append(record["display_text"])
        for warning in record["extraction_warnings"]:
            lines.append(f"EXTRACTION WARNING {warning['code']}: {warning['message']}")
    if not records:
        lines.append("No matching records.")
    return "\n".join(lines)
