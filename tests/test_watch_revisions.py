import sqlite3
import threading
from types import SimpleNamespace

import pytest

from scholium.config import Config
from scholium.indexing import ingest, freshness
from scholium.revisions import diff, history, recover_renames
from scholium.search import retrieve
from scholium.storage import IndexError, db_path
from scholium.watcher import Engine, Hints, relevant, run, watch_lock
from test_index import book, chapter, digest
from test_extraction import fixture


def test_schema1_readonly_refuses_and_migration_preserves_history(tmp_path):
    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Original evidence")
    revision = ingest(config)["results"][0]["revision"]
    with sqlite3.connect(db_path(config.data_dir)) as db:
        db.execute("DROP TABLE events")
        db.execute("PRAGMA user_version=1")
    before = digest(db_path(config.data_dir))
    with pytest.raises(IndexError, match="migration"):
        history(config, "CH01")
    assert digest(db_path(config.data_dir)) == before
    assert ingest(config)["results"][0]["revision"] == revision
    backups = list((config.data_dir / "backups").glob("*.sqlite3"))
    assert len(backups) == 1 and backups[0].stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert history(config, "CH01")["events"][0]["kind"] == "migration_baseline"
    assert retrieve(config, "search", query="evidence")["results"]


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    import scholium.storage as storage

    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Text")
    ingest(config)
    with sqlite3.connect(db_path(config.data_dir)) as db:
        db.execute("DROP TABLE events")
        db.execute("PRAGMA user_version=1")
    monkeypatch.setattr(storage, "EVENT_SCHEMA", "CREATE TABLE broken (")
    with pytest.raises(IndexError):
        ingest(config)
    with sqlite3.connect(db_path(config.data_dir)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_revision_diff_insert_notes_and_editorial_change(tmp_path):
    config = book(tmp_path)
    path = fixture(config.source_dirs[0] / "CH01.docx")
    first = ingest(config)["results"][0]["revision"]
    fixture(
        path,
        '<w:p><w:r><w:t>New opening</w:t></w:r></w:p><w:p><w:r><w:rPr><w:strike/></w:rPr><w:t>Größe</w:t><w:endnoteReference w:id="1"/></w:r></w:p>',
        "",
        '<w:endnote w:id="1"><w:p><w:r><w:t>Changed note</w:t></w:r></w:p></w:endnote>',
    )
    second = ingest(config)["results"][0]["revision"]
    before = digest(db_path(config.data_dir))
    result = diff(config, "CH01", first, second)
    assert result["blocks"] and result["notes"]
    assert result["from_revision"] == first and result["to_revision"] == second
    assert any(r["contains_struck_text"] for c in result["blocks"] for r in c["after"])
    note = next(c for c in result["notes"] if c["note_id"] == "endnote:1")
    assert note["after"]["text"] == "Changed note"
    assert not diff(config, "CH01", second, second)["blocks"]
    assert len(history(config, "CH01")["revisions"]) == 2
    assert digest(db_path(config.data_dir)) == before
    with pytest.raises(IndexError):
        diff(config, "CH01", first, "unknown")


def test_diff_detects_format_only_change_and_revert_events(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Same words")
    original = path.read_bytes()
    first = ingest(config)["results"][0]["revision"]
    fixture(path, "<w:p><w:r><w:rPr><w:strike/></w:rPr><w:t>Same words</w:t></w:r></w:p>", "", "")
    second = ingest(config)["results"][0]["revision"]
    result = diff(config, "CH01", first, second)
    assert result["blocks"][0]["text_unchanged"]
    path.write_bytes(original)
    ingest(config)
    listing = history(config, "CH01")
    assert len(listing["revisions"]) == 2 and len(listing["events"]) == 3
    assert listing["events"][-1]["from_revision"] == second
    assert listing["events"][-1]["to_revision"] == first


def test_zip_metadata_change_has_no_passage_diff(tmp_path):
    import zipfile

    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Unchanged content")
    first = ingest(config)["results"][0]["revision"]
    with zipfile.ZipFile(path, "a") as archive:
        archive.comment = b"Synthetic package metadata change"
    second = ingest(config)["results"][0]["revision"]
    result = diff(config, "CH01", first, second)
    assert result["source_only_change"] and not result["blocks"] and not result["notes"]


def test_unique_rename_preserves_identity_and_source_provenance(tmp_path):
    config = book(tmp_path)
    old = chapter(config.source_dirs[0] / "CH01.docx", "Evidence")
    first = ingest(config)["results"][0]["revision"]
    new = old.with_name("renamed.docx")
    old.rename(new)
    result = ingest(config)
    assert len(result["renames"]) == 1
    assert result["results"][0]["chapter"] == "CH01"
    assert result["results"][0]["revision"] == first
    hit = retrieve(config, "search", query="Evidence")["results"][0]
    assert hit["source_path"] == str(old) and hit["current_source_path"] == str(new)
    assert history(config, "CH01")["events"][-1]["kind"] == "renamed"
    assert freshness(config)["current"]


def test_ambiguous_copies_are_not_merged(tmp_path):
    config = book(tmp_path)
    old = chapter(config.source_dirs[0] / "old.docx", "Evidence")
    ingest(config)
    data = old.read_bytes()
    old.unlink()
    (old.parent / "copy1.docx").write_bytes(data)
    (old.parent / "copy2.docx").write_bytes(data)
    assert recover_renames(config) == []
    result = ingest(config)
    assert sum(r["state"] == "indexed" for r in result["results"]) == 2
    assert any(r["state"] == "missing" for r in result["results"])


def test_locked_root_cannot_trigger_rename_inference(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "old.docx", "Evidence")
    ingest(config)
    data = path.read_bytes()
    path.unlink()
    config.source_dirs[0].rmdir()
    other = tmp_path / "other"
    other.mkdir()
    (other / "new.docx").write_bytes(data)
    updated = Config(config.path, (*config.source_dirs, other), config.languages, config.data_dir)
    assert recover_renames(updated) == []


@pytest.mark.parametrize(
    "kind,src,dest,directory,expected",
    [
        ("modified", "~$chapter.docx", "", False, False),
        ("opened", "chapter.docx", "", False, False),
        ("modified", "notes.txt", "", False, False),
        ("moved", "temp.tmp", "chapter.docx", False, True),
        ("deleted", "chapter.docx", "", False, True),
        ("moved", "folder", "other", True, True),
    ],
)
def test_event_filter(kind, src, dest, directory, expected):
    event = SimpleNamespace(event_type=kind, src_path=src, dest_path=dest, is_directory=directory)
    assert relevant(event) is expected


def test_event_debounce(monkeypatch):
    import scholium.watcher as watcher

    clock = [10.0]
    monkeypatch.setattr(watcher.time, "monotonic", lambda: clock[0])
    hints = Hints()
    event = SimpleNamespace(
        event_type="modified", src_path="chapter.docx", dest_path="", is_directory=False
    )
    hints.on_any_event(event)
    assert not hints.consume_if_quiet(10.5, 1)
    clock[0] = 10.8
    hints.on_any_event(event)
    assert not hints.consume_if_quiet(11, 1)
    assert hints.consume_if_quiet(12, 1)
    assert not hints.consume_if_quiet(13, 1)


def test_rapid_saves_wait_for_final_stable_bytes(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Initial")
    ingest(config)
    events = []
    engine = Engine(config, lambda name, **data: events.append((name, data)), settle=1)
    chapter(path, "Intermediate")
    engine.reconcile(0)
    chapter(path, "Final")
    engine.tick(1)
    assert not engine.tick(1.5)
    assert engine.tick(2.1)
    assert retrieve(config, "search", query="Final")["results"]
    assert len(history(config, "CH01")["revisions"]) == 2


def test_partial_zip_retries_then_recovers_without_loss(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Known good")
    old = ingest(config)["results"][0]["revision"]
    path.write_bytes(b"partial")
    events = []
    engine = Engine(config, lambda name, **data: events.append((name, data)), settle=1, retries=2)
    engine.reconcile(0)
    assert not engine.tick(1)
    assert events[-1][0] == "retry"
    assert engine.tick(2)
    assert not engine.pending
    assert retrieve(config, "passage", chapter="CH01", block="1")["passage"]["revision"] == old
    engine.reconcile(3)
    assert not engine.pending  # Bounded attempts for unchanged broken bytes.
    chapter(path, "Recovered")
    engine.reconcile(4)
    engine.tick(5)
    assert freshness(config)["current"]
    assert retrieve(config, "search", query="Recovered")["results"]


def test_restart_and_missed_events_reconcile(tmp_path):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Before restart")
    ingest(config)
    chapter(path, "After restart")
    engine = Engine(config, lambda *a, **k: None, settle=0.1)
    engine.reconcile(0)
    engine.tick(0.2)
    assert retrieve(config, "search", query="After")["results"]
    path.unlink()
    engine.reconcile(1)
    assert freshness(config)["documents"][0]["state"] == "missing"
    chapter(path, "Restored")
    engine.reconcile(2)
    engine.tick(2.2)
    assert freshness(config)["current"]


def test_single_watcher_lock(tmp_path):
    config = book(tmp_path)
    with watch_lock(config):
        with pytest.raises(IndexError, match="Another watcher"):
            with watch_lock(config):
                pass
    with watch_lock(config):
        pass


@pytest.mark.parametrize("polling", [True, False])
def test_live_watcher_observes_replacement_save(tmp_path, polling):
    config = book(tmp_path)
    path = chapter(config.source_dirs[0] / "CH01.docx", "Before save")
    stop = threading.Event()
    events = []
    indexed = []

    def emit(event):
        events.append(event)
        if event["event"] == "ingest" and event["ok"]:
            indexed.extend(r for r in event["results"] if r["state"] == "indexed")
            if len(indexed) == 1:

                def replace_after_quiet_period():
                    temporary = chapter(config.source_dirs[0] / "save.tmp", "After save")
                    temporary.replace(path)

                timer = threading.Timer(0.3, replace_after_quiet_period)
                timer.daemon = True
                timer.start()
            if len(indexed) == 2:
                stop.set()

    result = run(
        config, settle=0.02, interval=0.05, duration=5, polling=polling, emit=emit, stop_event=stop
    )
    assert result == 0 and len(indexed) == 2
    assert retrieve(config, "search", query="After")["results"]
    assert events[-1]["event"] == "stopped"
    assert events[0]["mode"] == (
        "hash-reconciliation" if polling else "watchdog+hash-reconciliation"
    )


def test_history_diff_cli_and_short_watch(tmp_path, capsys):
    import json
    from scholium.cli import main

    config = book(tmp_path)
    config.path.write_text(
        'schema_version=1\n[manuscript]\nsource_dirs=["source"]\nlanguages=["en","de"]\n[storage]\ndata_dir="data"\n'
    )
    path = chapter(config.source_dirs[0] / "CH01.docx", "Before")
    first = ingest(config)["results"][0]["revision"]
    chapter(path, "After")
    second = ingest(config)["results"][0]["revision"]
    prefix = ["--config", str(config.path)]
    assert main([*prefix, "revisions", "--chapter", "CH01", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["revisions"]) == 2
    assert (
        main([*prefix, "diff", "--chapter", "CH01", "--from", first, "--to", second, "--json"]) == 0
    )
    assert json.loads(capsys.readouterr().out)["blocks"]
    assert (
        main(
            [
                *prefix,
                "watch",
                "--poll",
                "--duration",
                ".1",
                "--settle",
                ".02",
                "--interval",
                ".02",
                "--json",
            ]
        )
        == 0
    )
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[0]["event"] == "started" and events[-1]["event"] == "stopped"
    assert main([*prefix, "watch", "--interval", "nan", "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_native_start_failure_falls_back_to_reconciliation(tmp_path, monkeypatch):
    import scholium.watcher as watcher

    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Evidence")

    class BrokenObserver:
        def start(self):
            raise OSError("synthetic observer failure")

    monkeypatch.setattr(watcher, "Observer", BrokenObserver)
    events = []
    assert run(config, settle=0.01, interval=0.02, duration=0.2, emit=events.append) == 0
    assert any(e["event"] == "warning" for e in events)
    assert any(e.get("mode") == "hash-reconciliation" for e in events)
    assert freshness(config)["current"]


def test_new_unreadable_file_is_not_reported_current(tmp_path, monkeypatch):
    import scholium.indexing as indexing

    config = book(tmp_path)
    chapter(config.source_dirs[0] / "CH01.docx", "Evidence")

    def unreadable(_):
        raise PermissionError("synthetic locked file")

    monkeypatch.setattr(indexing, "source_hash", unreadable)
    state = freshness(config)
    assert not state["current"]
    assert state["documents"][0]["state"] == "unavailable"
