"""Read-only provenance audit; does not score scholarly answers or call a model.

Run with the project Python and --config FILE --output NEW_PRIVATE_DIRECTORY.
Outputs contain private manuscript text. The destination must not already exist.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scholium.config import load
from scholium.search import retrieve

TERMS = [
    "Goethe",
    "Hirschfeld",
    "Weimar",
    "Homosexualität",
    "Müller",
    "Kertbeny",
    "Ulrichs",
    "Platen",
    "Klaus Mann",
    "Brand",
    "Radszuweit",
    "Romanticism",
    "autobiography",
    "Ganymed",
    "Schlegel",
]


def run(config, output):
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    database = config.data_dir / "index.sqlite3"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    audit = []
    for term in TERMS:
        result = retrieve(config, "search", query=term, limit=100)
        evidence = []
        # Check up to five distinct chapters, including full note anchor context.
        seen = set()
        for hit in result["results"]:
            if hit["chapter"] in seen:
                continue
            seen.add(hit["chapter"])
            common = dict(chapter=hit["chapter"], revision=hit["revision"])
            if hit["kind"] == "block":
                context = retrieve(config, "passage", block=hit["locator"], **common)
                exact = context["passage"]
                anchors = [hit["locator"]]
            else:
                context = retrieve(config, "notes", note=hit["locator"], **common)
                exact = context["notes"][0]
                doc = retrieve(config, "export", **common)["documents"][0]
                anchors = [
                    b["id"]
                    for b in doc["blocks"]
                    if any(a["note_id"] == hit["locator"] for a in b["anchors"])
                ]
            assert exact == hit, "Search/retrieval provenance mismatch"
            doc = retrieve(config, "export", **common)["documents"][0]
            neighborhoods = []
            for anchor in anchors:
                position = next(i for i, b in enumerate(doc["blocks"]) if b["id"] == anchor)
                for block in doc["blocks"][max(0, position - 1) : position + 2]:
                    neighborhoods.append(retrieve(config, "passage", block=block["id"], **common))
            evidence.append(dict(hit=hit, context=context, neighborhoods=neighborhoods))
            if len(seen) == 5:
                break
        audit.append(
            dict(
                query=term,
                returned_hits=len(result["results"]),
                potentially_truncated=len(result["results"]) == 100,
                freshness=result["freshness"],
                evidence=evidence,
            )
        )
    # Known fabricated token tests empty retrieval, not manuscript-wide absence.
    empty = retrieve(config, "search", query="scholiumNonexistentProbe9f7c2")
    assert not empty["results"]
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    assert before == after, "Index changed during audit; rerun without concurrent ingestion"
    report = dict(
        schema_version=1,
        kind="provenance audit, not answer accuracy",
        queries=audit,
        empty_probe=empty,
        database_unchanged=True,
    )
    path = output / "evidence.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    path.chmod(0o600)
    print(
        json.dumps(
            dict(
                queries=len(audit),
                verified_records=sum(len(a["evidence"]) for a in audit),
                zero_hit_queries=[a["query"] for a in audit if not a["returned_hits"]],
                database_unchanged=True,
                output=str(path),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(load(args.config.resolve()), args.output.resolve())
