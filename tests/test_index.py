import hashlib
import json
import sqlite3

import pytest

from scholium.cli import main
from scholium.config import Config
from scholium.indexing import freshness, ingest, scan
from scholium.search import retrieve
from scholium.storage import IndexError, connect, db_path
from test_extraction import fixture


def book(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    return Config(tmp_path / "scholium.toml", (source,), ("en", "de"), tmp_path / "data")


def chapter(path, text):
    return fixture(path, f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>", "", "")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_multichapter_search_notes_and_idempotence(tmp_path):
    config = book(tmp_path)
    fixture(config.source_dirs[0] / "CH01.docx")
    chapter(config.source_dirs[0] / "CH02.docx", "Größe and Romanticism")
    first = ingest(config)
    assert first["ok"]
    assert len(retrieve(config, "search", query="Größe")["results"]) == 2
    notes = retrieve(config, "search", query="Müller")["results"]
    assert len(notes) == 1 and notes[0]["kind"] == "note"
    assert notes[0]["locator"] == "footnote:1"
    passage = retrieve(config, "passage", chapter="CH01", block="2")
    assert len(passage["linked_notes"]) == 2
    assert passage["passage"]["record"]["headings"] == ["Einführung"]
    assert passage["passage"]["revision"] == passage["linked_notes"][0]["revision"]
    assert (
        retrieve(config, "notes", chapter="CH01", note="endnote:1")["notes"][0]["text"]
        == "Endnote evidence."
    )
    assert all(r["state"] == "unchanged" for r in ingest(config)["results"])
    with connect(config.data_dir) as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM search_records").fetchone()[0] == 10
    assert all(r["state"] == "current" for r in freshness(config)["documents"])


def test_revisions_replace_current_search_and_keep_history(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Oldargument")
    old = ingest(config)["results"][0]["revision"]
    chapter(path, "Newargument")
    assert freshness(config)["documents"][0]["state"] == "stale"
    stale = retrieve(config, "search", query="Oldargument")
    assert not stale["freshness"]["current"] and len(stale["results"]) == 1
    new = ingest(config)["results"][0]["revision"]
    assert old != new
    assert not retrieve(config, "search", query="Oldargument")["results"]
    assert len(retrieve(config, "search", query="Newargument")["results"]) == 1
    historical = retrieve(config, "passage", chapter="CH01", block="1", revision=old)
    assert not historical["is_current_revision"]
    assert historical["passage"]["text"] == "Oldargument"
    chapter(path, "Oldargument")
    # ZIP creation timestamps may differ: preserve the actual original bytes in dedicated revert test.
    assert ingest(config)["ok"]


def test_failed_parse_and_missing_file_keep_good_index(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Known evidence")
    original = path.read_bytes()
    revision = ingest(config)["results"][0]["revision"]
    path.write_bytes(b"broken partial ZIP")
    failed = ingest(config)
    assert not failed["ok"]
    assert failed["results"][0]["retained_revision"] == revision
    assert freshness(config)["documents"][0]["state"] == "error"
    assert retrieve(config, "search", query="evidence")["results"][0]["revision"] == revision
    path.unlink()
    assert freshness(config)["documents"][0]["state"] == "missing"
    reconciliation = ingest(config)
    assert not reconciliation["ok"]
    assert reconciliation["results"][0]["state"] == "missing"
    assert (
        retrieve(config, "passage", chapter="CH01", block="1")["passage"]["text"]
        == "Known evidence"
    )
    path.write_bytes(original)
    assert ingest(config)["results"][0]["state"] == "unchanged"
    assert freshness(config)["current"]


def test_transaction_rollback_after_fts_insert(tmp_path, monkeypatch):
    import scholium.indexing as indexing

    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Committed")
    revision = ingest(config)["results"][0]["revision"]
    chapter(path, "Uncommitted")
    original_save = indexing.save_revision

    def failing_save(*args):
        original_save(*args)
        raise RuntimeError("simulated interruption before commit")

    monkeypatch.setattr(indexing, "save_revision", failing_save)
    with pytest.raises(RuntimeError):
        ingest(config)
    with connect(config.data_dir) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1
        assert db.execute("SELECT current_revision FROM documents").fetchone()[0] == revision
        assert (
            db.execute(
                "SELECT count(*) FROM search_records WHERE search_records MATCH 'Uncommitted'"
            ).fetchone()[0]
            == 0
        )
    assert len(retrieve(config, "search", query="Committed")["results"]) == 1


def test_retrieval_writes_nothing_and_hashes_sources(tmp_path):
    config = book(tmp_path)
    source = fixture(config.source_dirs[0] / "CH01.docx")
    source_before = digest(source)
    ingest(config)
    before = {p: (digest(p), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    freshness(config)
    for command, options in [
        ("search", {"query": "ideas"}),
        ("passage", {"chapter": "CH01", "block": "2"}),
        ("notes", {"chapter": "CH01"}),
        ("export", {}),
    ]:
        assert retrieve(config, command, **options)["ok"]
    after = {p: (digest(p), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert digest(source) == source_before
    assert config.data_dir.stat().st_mode & 0o777 == 0o700
    assert db_path(config.data_dir).stat().st_mode & 0o777 == 0o600


def test_discovery_deduplicates_and_ignores_lock_files(tmp_path):
    config = book(tmp_path)
    nested = config.source_dirs[0] / "nested"
    nested.mkdir()
    chapter(nested / "chapter.DOCX", "Evidence")
    (nested / "~$chapter.docx").write_bytes(b"lock")
    overlapping = Config(
        config.path, (*config.source_dirs, nested), config.languages, config.data_dir
    )
    files, errors = scan(overlapping)
    assert len(files) == 1 and not errors
    assert len(ingest(overlapping)["results"]) == 1


def test_duplicate_filenames_get_distinct_keys(tmp_path):
    config = book(tmp_path)
    for sub in ["a", "b"]:
        folder = config.source_dirs[0] / sub
        folder.mkdir()
        chapter(folder / "chapter.docx", "Evidence")
    results = ingest(config)["results"]
    assert len({r["chapter"] for r in results}) == 2
    assert len(retrieve(config, "search", query="Evidence")["results"]) == 2


def test_unicode_and_safe_query_semantics(tmp_path):
    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Müller Straße Enlightenment Romanticism")
    ingest(config)
    assert retrieve(config, "search", query="MÜLLER")["results"]
    assert not retrieve(config, "search", query="Muller")["results"]
    assert not retrieve(config, "search", query="Strasse")["results"]
    assert retrieve(config, "search", query="romanticism enlightenment")["results"]
    assert not retrieve(config, "search", query='" OR missing')["results"]
    with pytest.raises(IndexError):
        retrieve(config, "search", query="***")
    with pytest.raises(IndexError):
        retrieve(config, "search", query="Müller", limit=0)


def test_struck_text_is_explicit_in_search(tmp_path):
    config = book(tmp_path)
    fixture(
        config.source_dirs[0] / "CH01.docx",
        "<w:p><w:r><w:rPr><w:strike/></w:rPr><w:t>Abandoned claim</w:t></w:r></w:p>",
        "",
        "",
    )
    ingest(config)
    hit = retrieve(config, "search", query="Abandoned")["results"][0]
    assert hit["contains_struck_text"]
    assert hit["display_text"] == "[STRIKETHROUGH]Abandoned claim[/STRIKETHROUGH]"
    assert hit["record"]["formatting"][0]["properties"]["strike"]


def test_new_files_and_unavailable_roots_warn(tmp_path):
    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Evidence")
    ingest(config)
    chapter(config.source_dirs[0] / "CH02.docx", "More evidence")
    assert not retrieve(config, "search", query="Evidence")["freshness"]["current"]
    for path in config.source_dirs[0].iterdir():
        path.unlink()
    config.source_dirs[0].rmdir()
    state = freshness(config)
    assert state["scan_errors"]
    assert state["documents"][0]["state"] == "missing"


def test_unknown_index_schema_is_not_modified(tmp_path):
    config = book(tmp_path)
    config.data_dir.mkdir()
    db = sqlite3.connect(db_path(config.data_dir))
    db.execute("PRAGMA user_version=999")
    db.close()
    before = digest(db_path(config.data_dir))
    with pytest.raises(IndexError, match="Unsupported"):
        ingest(config)
    assert digest(db_path(config.data_dir)) == before


def test_revision_must_belong_to_selected_chapter(tmp_path):
    config = book(tmp_path)
    chapter(config.source_dirs[0] / "A.docx", "A")
    chapter(config.source_dirs[0] / "B.docx", "B")
    a_revision = ingest(config)["results"][0]["revision"]
    with pytest.raises(IndexError):
        retrieve(config, "passage", chapter="B", block="1", revision=a_revision)


def test_cli_workflow_json_and_exit_codes(tmp_path, capsys):
    config = book(tmp_path)
    config.path.write_text(
        'schema_version=1\n[manuscript]\nsource_dirs=["source"]\nlanguages=["en","de"]\n[storage]\ndata_dir="data"\n'
    )
    chapter(config.source_dirs[0] / "CH01.docx", "Evidence")
    prefix = ["--config", str(config.path)]
    assert main([*prefix, "status", "--json"]) == 1
    assert not json.loads(capsys.readouterr().out)["ok"]
    assert main([*prefix, "ingest", "--all", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert main([*prefix, "search", "Evidence", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["results"]) == 1
    assert main([*prefix, "export", "--format", "json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["documents"]) == 1
    assert main([*prefix, "passage", "--chapter", "missing", "--block", "1", "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_process_interruption_rolls_back_on_next_ingest(tmp_path):
    import subprocess
    import sys

    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Committed evidence")
    revision = ingest(config)["results"][0]["revision"]
    program = """import sqlite3,sys,os
c=sqlite3.connect(sys.argv[1])
c.execute("PRAGMA cache_size=1")
c.execute("BEGIN IMMEDIATE")
c.execute("UPDATE revisions SET canonical_json=?", ("x"*4000000,))
os._exit(7)
"""
    result = subprocess.run([sys.executable, "-c", program, str(db_path(config.data_dir))])
    assert result.returncode == 7
    assert ingest(config)["results"][0]["state"] == "unchanged"
    assert retrieve(config, "passage", chapter="CH01", block="1")["passage"]["revision"] == revision
    with connect(config.data_dir) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_source_change_during_commit_keeps_previous_revision(tmp_path, monkeypatch):
    import scholium.indexing as indexing

    config = book(tmp_path)
    source = chapter(config.source_dirs[0] / "CH01.docx", "Original")
    revision = ingest(config)["results"][0]["revision"]
    chapter(source, "Intended update")
    save = indexing.save_revision

    def change_during_save(*args):
        result = save(*args)
        source.write_bytes(b"Word is still saving")
        return result

    monkeypatch.setattr(indexing, "save_revision", change_during_save)
    result = ingest(config)
    assert not result["ok"]
    assert result["results"][0]["retained_revision"] == revision
    assert retrieve(config, "passage", chapter="CH01", block="1")["passage"]["text"] == "Original"


def test_reverting_bytes_reuses_revision_and_identity(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "First")
    original = path.read_bytes()
    first = ingest(config)["results"][0]["revision"]
    chapter(path, "Second")
    second = ingest(config)["results"][0]["revision"]
    path.write_bytes(original)
    reverted = ingest(config)["results"][0]["revision"]
    assert first == reverted and second != first
    with connect(config.data_dir) as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 1


def test_readonly_status_does_not_create_empty_database(tmp_path):
    config = book(tmp_path)
    assert not freshness(config)["current"]
    assert not config.data_dir.exists()
    with pytest.raises(IndexError, match="No index"):
        retrieve(config, "search", query="anything")
    assert not config.data_dir.exists()


def test_explicit_file_and_out_of_scope_protection(tmp_path):
    config = book(tmp_path)
    a = chapter(config.source_dirs[0] / "A.docx", "First")
    chapter(config.source_dirs[0] / "B.docx", "Second")
    assert len(ingest(config, str(a))["results"]) == 1
    assert not freshness(config)["current"]
    outside = chapter(tmp_path / "outside.docx", "External")
    with pytest.raises(IndexError):
        ingest(config, str(outside))
    (config.source_dirs[0] / "link.docx").symlink_to(outside)
    assert scan(config)[1]
    assert not ingest(config)["ok"]
