"""Local, explicitly imported scholarly analysis; never calls a model provider."""

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import json
import os
import sqlite3
import uuid

from .indexing import freshness
from .search import document_for, record_result, retrieve, freshness_message
from .storage import IndexError, connect
from .revisions import diff

KINDS = (
    "summary",
    "argument",
    "chronology",
    "person",
    "text",
    "movement",
    "concept",
    "influence",
    "citation",
    "finding",
)
BASES = ("verbatim", "author_interpretation", "cited_source_assertion", "ai_hypothesis")


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database(config, write=False):
    from .locks import book_lock

    with book_lock(config.data_dir) if write else nullcontext():
        with _database(config, write) as db:
            yield db


@contextmanager
def _database(config, write=False):
    path = config.data_dir / "analysis.sqlite3"
    if not write and not path.exists():
        yield None
        return
    if path.is_symlink():
        raise IndexError("Analysis database must not be a symlink.")
    if write:
        config.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
    try:
        db = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True)
    except sqlite3.Error as exc:
        raise IndexError("Cannot open analysis storage; check permissions and integrity.") from exc
    db.row_factory = sqlite3.Row
    try:
        version = db.execute("pragma user_version").fetchone()[0]
        if version == 0 and write:
            if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise IndexError("Unrecognized analysis database; keep it unchanged.")
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE analyses(id TEXT PRIMARY KEY, created TEXT, payload TEXT)")
                db.execute(
                    "CREATE TABLE reviews(id INTEGER PRIMARY KEY, analysis_id TEXT, item_id TEXT, state TEXT, comment TEXT, created TEXT)"
                )
                db.execute("pragma user_version=1")
                db.execute("pragma application_id=1396918349")
        elif version != 1 or db.execute("pragma application_id").fetchone()[0] != 1396918349:
            raise IndexError("Unsupported analysis database schema; keep it unchanged.")
        yield db
    except sqlite3.Error as exc:
        raise IndexError(
            "Analysis storage failed; check permissions and database integrity."
        ) from exc
    finally:
        db.close()


def template():
    return dict(
        schema_version=1,
        title="Describe this analysis",
        producer={
            "kind": "codex_conversation",
            "name": "interactive Codex",
            "method": "Read cited passages and notes in conversation",
        },
        coverage="Describe chapters/sections read and omissions",
        dependencies=[{"chapter": "CHAPTER", "revision": "REVISION"}],
        items=[
            dict(
                id="s1",
                kind="summary",
                basis="ai_hypothesis",
                text="Replace with an evidence-based assertion",
                evidence=[dict(chapter="CHAPTER", revision="REVISION", locator="b000001")],
                links=[],
            )
        ],
    )


def required_text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 50000:
        raise IndexError(f"{label} must be nonempty text (maximum 50000 characters).")


def validate(config, raw):
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "title",
        "producer",
        "coverage",
        "dependencies",
        "items",
    }:
        raise IndexError(
            "Analysis requires schema_version, title, producer, coverage, dependencies and items only."
        )
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise IndexError("Analysis schema_version must be 1.")
    for key in ("title", "coverage"):
        required_text(raw[key], key)
    producer = raw["producer"]
    if (
        not isinstance(producer, dict)
        or set(producer) != {"kind", "name", "method"}
        or producer["kind"] not in ("human", "codex_conversation")
    ):
        raise IndexError(
            "Producer must identify human or codex_conversation, name and method; no API provider is enabled."
        )
    for key in ("name", "method"):
        required_text(producer[key], key)
    if not isinstance(raw["dependencies"], list) or not raw["dependencies"]:
        raise IndexError("Declare at least one chapter/revision dependency, even for no finding.")
    if not isinstance(raw["items"], list) or len(raw["items"]) > 1000:
        raise IndexError("items must be a list with at most 1000 assertions.")
    result = json.loads(json.dumps(raw))
    with connect(config.data_dir) as db:
        deps = {}
        for dep in raw["dependencies"]:
            if not isinstance(dep, dict) or set(dep) not in (
                {"chapter", "revision"},
                {"chapter", "revision", "role"},
            ):
                raise IndexError(
                    "Each dependency requires chapter and revision, with optional current/historical role."
                )
            if dep.get("role", "current") not in ("current", "historical"):
                raise IndexError("Dependency role must be current or historical.")
            for key in ("chapter", "revision"):
                required_text(dep[key], key)
            doc, _ = document_for(db, dep["chapter"], dep["revision"])
            doc["dependency_role"] = dep.get("role", "current")
            deps[(doc["chapter"], doc["revision"])] = doc
        result["dependencies"] = [
            dict(
                chapter=d["chapter"],
                document_id=d["document_id"],
                revision=d["revision"],
                source_hash=d["source"]["sha256"],
                role=d["dependency_role"],
            )
            for d in deps.values()
        ]
        if not any(d["dependency_role"] == "current" for d in deps.values()):
            raise IndexError("At least one dependency must have role current.")
        current_docs = {
            d["document_id"] for d in deps.values() if d["dependency_role"] == "current"
        }
        if any(d["document_id"] not in current_docs for d in deps.values()):
            raise IndexError(
                "Every historical dependency needs a current-role dependency for the same document."
            )
        ids = set()
        for item in result["items"]:
            if not isinstance(item, dict) or set(item) != {
                "id",
                "kind",
                "basis",
                "text",
                "evidence",
                "links",
            }:
                raise IndexError(
                    "Each item requires id, kind, basis, text, evidence and links only."
                )
            for key in ("id", "text"):
                required_text(item[key], key)
            if item["id"] in ids:
                raise IndexError("Item IDs must be unique.")
            ids.add(item["id"])
            if item["kind"] not in KINDS or item["basis"] not in BASES:
                raise IndexError("Unknown assertion kind or basis.")
            if not isinstance(item["evidence"], list) or not item["evidence"]:
                raise IndexError("Every assertion requires passage or note evidence.")
            if not isinstance(item["links"], list):
                raise IndexError("links must be a list of item IDs.")
            resolved = []
            for ref in item["evidence"]:
                if not isinstance(ref, dict) or set(ref) != {"chapter", "revision", "locator"}:
                    raise IndexError("Evidence requires chapter, revision and locator only.")
                for key in ("chapter", "revision", "locator"):
                    required_text(ref[key], key)
                doc = deps.get((ref["chapter"], ref["revision"]))
                if doc is None:
                    raise IndexError(
                        "Evidence must use a declared canonical chapter/revision dependency."
                    )
                found = [
                    (r, k)
                    for k, records in [("block", doc["blocks"]), ("note", doc["notes"])]
                    for r in records
                    if r["id"] == ref["locator"]
                ]
                if len(found) != 1:
                    raise IndexError("Evidence locator does not exist in the declared revision.")
                record, kind = found[0]
                resolved.append(record_result(doc, record, kind))
            if item["basis"] == "verbatim" and not any(item["text"] in r["text"] for r in resolved):
                raise IndexError("Verbatim assertion must be an exact substring of a cited record.")
            item["evidence"] = resolved
        if any(
            not isinstance(link, str) or link not in ids
            for item in result["items"]
            for link in item["links"]
        ):
            raise IndexError("Every map link must name an existing item ID.")
    return result


def import_file(config, path):
    if path.stat().st_size > 5 * 1024 * 1024:
        raise IndexError("Analysis input exceeds 5 MiB.")
    try:
        raw = json.loads(path.read_text())
    except (ValueError, UnicodeError) as exc:
        raise IndexError("Analysis input must be valid UTF-8 JSON.") from exc
    payload = validate(config, raw)
    identifier = str(uuid.uuid4())
    with database(config, True) as db, db:
        db.execute("INSERT INTO analyses VALUES(?,?,?)", (identifier, now(), json.dumps(payload)))
    return show(config, identifier)


def show(config, identifier=None):
    state = freshness(config)
    by_id = {d.get("document_id"): d for d in state["documents"]}
    analyses = []
    with database(config) as db:
        rows = (
            []
            if db is None
            else db.execute("SELECT * FROM analyses ORDER BY created,id").fetchall()
        )
        for row in rows:
            if identifier and row["id"] != identifier:
                continue
            payload = json.loads(row["payload"])
            reasons = []
            for dep in payload["dependencies"]:
                if dep.get("role") == "historical":
                    continue
                current = by_id.get(dep["document_id"])
                if (
                    not current
                    or current["state"] != "current"
                    or current["revision"] != dep["revision"]
                    or current.get("observed_hash") != dep["source_hash"]
                ):
                    reasons.append(
                        dict(
                            chapter=dep["chapter"],
                            reason="Source unavailable, changed or selected revision no longer current",
                        )
                    )
            if state["scan_errors"]:
                reasons.append(dict(chapter=None, reason="Source scan incomplete"))
            reviews = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM reviews WHERE analysis_id=? ORDER BY id", (row["id"],)
                )
            ]
            for item in payload["items"]:
                matches = [r for r in reviews if r["item_id"] == item["id"]]
                item["review_state"] = matches[-1]["state"] if matches else "open"
            analyses.append(
                dict(
                    id=row["id"],
                    created=row["created"],
                    current=not reasons,
                    stale_reasons=reasons,
                    analysis=payload,
                    reviews=reviews,
                )
            )
    if identifier and not analyses:
        raise IndexError("Analysis ID not found.")
    return dict(
        schema_version=1,
        command="analysis",
        freshness=state,
        analyses=analyses,
        no_finding=bool(identifier and not analyses[0]["analysis"]["items"]),
    )


def review(config, identifier, item_id, state, comment):
    report = show(config, identifier)
    if state not in ("open", "accepted", "dismissed"):
        raise IndexError("Review state must be open, accepted or dismissed.")
    if item_id not in {i["id"] for i in report["analyses"][0]["analysis"]["items"]}:
        raise IndexError("Review item ID not found.")
    if not isinstance(comment, str) or len(comment) > 50000:
        raise IndexError("Review comment must be text up to 50000 characters.")
    with database(config, True) as db, db:
        db.execute(
            "INSERT INTO reviews(analysis_id,item_id,state,comment,created) VALUES(?,?,?,?,?)",
            (identifier, item_id, state, comment, now()),
        )
    return show(config, identifier)


def impact(config, chapter, old, new, queries, limit=10):
    if not queries or len(queries) > 10 or not 1 <= limit <= 100:
        raise IndexError("Use 1–10 explicit queries and limit 1–100.")
    changes = diff(config, chapter, old, new)
    with connect(config.data_dir) as db:
        selected, target_current = document_for(db, chapter, new)
    candidates = {}
    searches = []
    no_extracted_change = not (
        changes["blocks"]
        or changes["notes"]
        or changes["parser_changed"]
        or changes["warnings_before"] != changes["warnings_after"]
    )
    for query in [] if no_extracted_change else queries:
        result = retrieve(config, "search", query=query, limit=100)
        searches.append(
            dict(query=query, returned=len(result["results"]), capped=len(result["results"]) == 100)
        )
        for record in result["results"]:
            if record["document_id"] == selected["document_id"]:
                continue
            key = (record["document_id"], record["revision"], record["locator"])
            if key not in candidates:
                candidates[key] = dict(
                    evidence=record,
                    matched_queries=[],
                    assessment="unassessed lexical candidate; not an established implication or contradiction",
                )
            if query not in candidates[key]["matched_queries"]:
                candidates[key]["matched_queries"].append(query)
    ranked = sorted(
        candidates.values(), key=lambda c: (-len(c["matched_queries"]), c["evidence"]["citation"])
    )
    return dict(
        schema_version=1,
        command="impact",
        target_is_current_revision=target_current,
        freshness=freshness(config),
        changes=changes,
        queries=searches,
        candidates=ranked[:limit],
        candidate_count=len(ranked),
        truncated=len(ranked) > limit or any(s["capped"] for s in searches),
        no_finding=not ranked,
        no_extracted_change=no_extracted_change,
        ranking="Number of distinct supplied queries matched, then citation; lexical relevance only",
        next_step="Read changed passages and candidate context/notes in conversation. Import assessed suggestions as analysis finding items with both revisions and candidate revisions as dependencies (old revision role historical, new and related revisions role current). No automatic inference or API call occurred.",
    )


def readable(result):
    lines = freshness_message(result["freshness"])
    if result["command"] == "impact":
        lines += [
            "# Editorial impact candidates",
            "Suggestions for review, not established contradictions.",
            "Target revision is current in the index."
            if result["target_is_current_revision"]
            else "HISTORICAL target revision: not the latest indexed chapter.",
            "## Changes",
            json.dumps(result["changes"], ensure_ascii=False, indent=2),
            "## Candidate related passages",
            "No extracted change: related-passage search skipped."
            if result["no_extracted_change"]
            else "Changed evidence supplied below.",
        ]
        for c in result["candidates"]:
            lines += [c["evidence"]["citation"], c["evidence"]["display_text"], c["assessment"]]
        lines += [
            "No finding in the supplied query scope."
            if result["no_finding"]
            else result["ranking"],
            f"Coverage truncated: {result['truncated']}",
            result["next_step"],
        ]
    else:
        if not result["analyses"]:
            lines += ["No saved analyses. Ask Codex to read a chapter and save a cited summary."]
        for entry in result["analyses"]:
            a = entry["analysis"]
            lines += [
                f"# {a['title']}",
                f"Analysis {entry['id']} — {'current' if entry['current'] else 'OUTDATED'}",
                a["coverage"],
                f"Producer: {a['producer']['kind']} / {a['producer']['name']}; method: {a['producer']['method']}",
                "Dependencies: "
                + "; ".join(
                    f"{d['chapter']} · rev {d['revision']} ({d['role']})" for d in a["dependencies"]
                ),
                "Interpretations are supplied by the named producer; citations are validated, truth is not certified.",
            ]
            if not a["items"]:
                lines += ["No finding in the declared coverage."]
            for item in a["items"]:
                lines += [
                    f"## {item['id']}: {item['kind']} / {item['basis']} / {item['review_state']}",
                    item["text"],
                ]
                for ref in item["evidence"]:
                    lines += [ref["citation"], ref["display_text"]]
                    lines += [
                        f"Extraction warning: {w['code']} — {w['message']}"
                        for w in ref["extraction_warnings"]
                    ]
                if item["links"]:
                    lines += ["Links: " + ", ".join(item["links"])]
    return "\n\n".join(lines)
