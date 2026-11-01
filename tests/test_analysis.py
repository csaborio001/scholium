import copy
import json
import sqlite3

import pytest

from scholium import analysis
from scholium.cli import main
from scholium.indexing import ingest
from scholium.search import retrieve
from scholium.storage import IndexError
from test_index import book, chapter, digest


def prepared(tmp_path):
    c = book(tmp_path)
    chapter(c.source_dirs[0] / "A.docx", "The society began in 1900. Identity is contextual.")
    ingest(c)
    rev = retrieve(c, "export", chapter="A")["documents"][0]["revision"]
    data = analysis.template()
    data["dependencies"] = [dict(chapter="A", revision=rev)]
    data["items"][0].update(
        text="The society began in 1900.",
        basis="verbatim",
        evidence=[dict(chapter="A", revision=rev, locator="b000001")],
    )
    return c, data


def save(c, data, name="input.json"):
    path = c.path.parent / name
    path.write_text(json.dumps(data))
    return analysis.import_file(c, path)


def test_import_roundtrip_and_readonly(tmp_path):
    c, data = prepared(tmp_path)
    before = digest(c.data_dir / "index.sqlite3")
    result = save(c, data)
    entry = result["analyses"][0]
    assert entry["current"]
    assert entry["analysis"]["items"][0]["evidence"][0]["citation"].endswith("b000001")
    assert entry["analysis"]["items"][0]["review_state"] == "open"
    side = digest(c.data_dir / "analysis.sqlite3")
    assert analysis.show(c, entry["id"])["analyses"] == result["analyses"]
    assert side == digest(c.data_dir / "analysis.sqlite3")
    assert before == digest(c.data_dir / "index.sqlite3")
    assert (c.data_dir / "analysis.sqlite3").stat().st_mode & 0o777 == 0o600
    assert "verbatim" in analysis.readable(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_locator",
        "fake_quote",
        "fake_revision",
        "unknown_link",
        "provider",
        "duplicate",
        "no_evidence",
        "bad_type",
    ],
)
def test_bad_input_does_not_create_storage(tmp_path, mutation):
    c, d = prepared(tmp_path)
    if mutation == "missing_locator":
        d["items"][0]["evidence"][0]["locator"] = "b999999"
    elif mutation == "fake_quote":
        d["items"][0]["text"] = "Invented quotation"
    elif mutation == "fake_revision":
        d["dependencies"][0]["revision"] = "invented"
    elif mutation == "unknown_link":
        d["items"][0]["links"] = ["missing"]
    elif mutation == "provider":
        d["producer"]["kind"] = "unattended_api"
    elif mutation == "duplicate":
        d["items"].append(copy.deepcopy(d["items"][0]))
    elif mutation == "no_evidence":
        d["items"][0]["evidence"] = []
    else:
        d["dependencies"] = "wrong"
    with pytest.raises(IndexError):
        save(c, d)
    assert not (c.data_dir / "analysis.sqlite3").exists()


def test_stale_before_and_after_ingestion_and_new_analysis(tmp_path):
    c, d = prepared(tmp_path)
    old = save(c, d)["analyses"][0]["id"]
    chapter(c.source_dirs[0] / "A.docx", "The society began in 1901.")
    assert not analysis.show(c, old)["analyses"][0]["current"]
    ingest(c)
    assert not analysis.show(c, old)["analyses"][0]["current"]
    newrev = retrieve(c, "export", chapter="A")["documents"][0]["revision"]
    d["dependencies"].append(dict(chapter="A", revision=newrev))
    d["dependencies"][0]["role"] = "historical"
    d["items"][0]["kind"] = "finding"
    new = save(c, d)["analyses"][0]
    assert new["current"] and new["id"] != old
    # Historical evidence remains available without treating the old revision as current.
    assert new["analysis"]["dependencies"][0]["role"] == "historical"
    (c.source_dirs[0] / "A.docx").unlink()
    assert not analysis.show(c, new["id"])["analyses"][0]["current"]


def test_review_history_preserves_payload_and_staleness(tmp_path):
    c, d = prepared(tmp_path)
    id = save(c, d)["analyses"][0]["id"]
    analysis.review(c, id, "s1", "accepted", "Author approves")
    r = analysis.review(c, id, "s1", "dismissed", "Author changes assessment")["analyses"][0]
    assert [r["state"] for r in r["reviews"]] == ["accepted", "dismissed"]
    assert r["analysis"]["items"][0]["text"] == d["items"][0]["text"]
    chapter(c.source_dirs[0] / "A.docx", "Changed text")
    assert not analysis.show(c, id)["analyses"][0]["current"]
    with pytest.raises(IndexError):
        analysis.review(c, id, "unknown", "accepted", "")


def test_empty_analysis_and_absent_database(tmp_path):
    c, d = prepared(tmp_path)
    assert analysis.show(c)["analyses"] == []
    assert not (c.data_dir / "analysis.sqlite3").exists()
    d["items"] = []
    r = save(c, d)
    assert r["no_finding"]
    assert "No finding" in analysis.readable(r)


def test_impact_clear_difference_nuance_and_unrelated(tmp_path):
    c, d = prepared(tmp_path)
    old = d["dependencies"][0]["revision"]
    chapter(c.source_dirs[0] / "B.docx", "The society began in 1900.")
    chapter(
        c.source_dirs[0] / "C.docx", "Identity can be contextual in literature but fixed in law."
    )
    chapter(c.source_dirs[0] / "D.docx", "Gardens grow in spring.")
    chapter(c.source_dirs[0] / "A.docx", "The society began in 1901. Identity is fixed.")
    ingest(c)
    new = retrieve(c, "export", chapter="A")["documents"][0]["revision"]
    r = analysis.impact(c, "A", old, new, ["society", "Identity"])
    assert {x["evidence"]["chapter"] for x in r["candidates"]} == {"B", "C"}
    assert all("unassessed" in x["assessment"] for x in r["candidates"])
    assert r["changes"]["blocks"]
    historical = analysis.impact(c, "A", new, old, ["society"])
    assert not historical["target_is_current_revision"]
    assert "HISTORICAL target" in analysis.readable(historical)
    assert analysis.impact(c, "A", old, new, ["nonexistentprobe"])["no_finding"]
    assert "Gardens" not in analysis.readable(r)
    # Ranking is lexical and never certifies even the clear date discrepancy.
    assert "not established contradictions" in analysis.readable(r)


def test_cli_and_failure_contract(tmp_path, capsys):
    c, d = prepared(tmp_path)
    c.path.write_text(
        'schema_version=1\n[manuscript]\nsource_dirs=["source"]\nlanguages=["en"]\n[storage]\ndata_dir="data"\n'
    )
    f = c.path.parent / "analysis.json"
    f.write_text(json.dumps(d))
    base = ["--config", str(c.path), "analysis"]
    assert main(base + ["import", str(f), "--json"]) == 0
    id = json.loads(capsys.readouterr().out)["analyses"][0]["id"]
    assert main(base + ["show", "--id", id, "--json"]) == 0
    capsys.readouterr()
    f.write_text("{invalid")
    assert main(base + ["import", str(f), "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]
    chapter(c.source_dirs[0] / "A.docx", "Changed")
    assert main(base + ["list", "--json"]) == 1
    capsys.readouterr()
    assert main(["analysis", "template"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == 1


def test_unknown_analysis_database_untouched(tmp_path):
    c, d = prepared(tmp_path)
    save(c, d)
    path = c.data_dir / "analysis.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("pragma user_version=99")
    before = digest(path)
    with pytest.raises(IndexError):
        save(c, d)
    assert before == digest(path)


def test_historical_dependency_cannot_bypass_current_source_tracking(tmp_path):
    c, d = prepared(tmp_path)
    d["dependencies"][0]["role"] = "historical"
    with pytest.raises(IndexError):
        save(c, d)
    chapter(c.source_dirs[0] / "B.docx", "Another chapter")
    ingest(c)
    rev = retrieve(c, "export", chapter="B")["documents"][0]["revision"]
    d["dependencies"].append(dict(chapter="B", revision=rev))
    with pytest.raises(IndexError):
        save(c, d)


def test_same_revision_has_no_impact_candidates(tmp_path):
    c, d = prepared(tmp_path)
    chapter(c.source_dirs[0] / "B.docx", "The society began in 1900.")
    ingest(c)
    rev = d["dependencies"][0]["revision"]
    r = analysis.impact(c, "A", rev, rev, ["society"])
    assert r["no_extracted_change"] and r["no_finding"]
    assert not r["candidates"]
