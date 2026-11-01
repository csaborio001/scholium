from dataclasses import replace
import json
from pathlib import Path
import plistlib
import sqlite3

import pytest

from scholium import maintenance, integration, analysis
from scholium.cli import main
from scholium.config import TEMPLATE
from scholium.locks import book_lock
from scholium.search import retrieve
from scholium.storage import IndexError, connect
from test_analysis import prepared, save
from test_index import digest


def configured(tmp_path):
    c, d = prepared(tmp_path)
    c.path.write_text(
        TEMPLATE.replace("source_dirs = []", 'source_dirs = ["source"]').replace(
            'data_dir = ".scholium"', 'data_dir = "data"'
        )
    )
    id = save(c, d)["analyses"][0]["id"]
    analysis.review(c, id, "s1", "accepted", "Synthetic review")
    return c, id


def test_backup_restore_keeps_history_and_active_data(tmp_path):
    c, id = configured(tmp_path)
    before = {p.name: digest(p) for p in c.data_dir.glob("*.sqlite3")}
    result = maintenance.backup(c)
    folder = Path(result["directory"])
    assert result["analysis"]["analyses"] == 1 and result["analysis"]["reviews"] == 1
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in folder.iterdir())
    assert folder.stat().st_mode & 0o777 == 0o700
    restored = tmp_path / "restored"
    maintenance.restore(c, folder, restored)
    rc = replace(c, data_dir=restored)
    assert retrieve(rc, "search", query="society")["results"]
    assert (
        analysis.show(rc, id)["analyses"][0]["analysis"]["items"][0]["review_state"] == "accepted"
    )
    assert before == {p.name: digest(p) for p in c.data_dir.glob("*.sqlite3")}


@pytest.mark.parametrize(
    "damage", ["bytes", "traversal", "symlink", "incomplete", "missing", "foreign_schema"]
)
def test_invalid_backup_rejected_without_restore(tmp_path, damage):
    c, _ = configured(tmp_path)
    folder = Path(maintenance.backup(c)["directory"])
    target = folder / "index.sqlite3"
    if damage == "bytes":
        target.write_bytes(b"broken")
    elif damage == "traversal":
        data = json.loads((folder / "manifest.json").read_text())
        data["files"]["../escape"] = {}
        (folder / "manifest.json").write_text(json.dumps(data))
    elif damage == "symlink":
        target.unlink()
        target.symlink_to(c.data_dir / "index.sqlite3")
    elif damage == "incomplete":
        (folder / ".incomplete").write_text("interrupted")
    elif damage == "missing":
        target.unlink()
    else:
        with sqlite3.connect(target) as db:
            db.execute("pragma user_version=999")
        data = json.loads((folder / "manifest.json").read_text())
        data["files"]["index.sqlite3"]["sha256"] = maintenance.digest(target)
        (folder / "manifest.json").write_text(json.dumps(data))
    out = tmp_path / "recovery"
    with pytest.raises(IndexError):
        maintenance.restore(c, folder, out)
    assert not out.exists()


def test_restore_recovers_when_active_index_corrupt(tmp_path):
    c, id = configured(tmp_path)
    folder = Path(maintenance.backup(c)["directory"])
    active = c.data_dir / "index.sqlite3"
    active.write_bytes(b"corrupt synthetic database")
    with pytest.raises(IndexError):
        retrieve(c, "search", query="society")
    out = tmp_path / "recovery"
    maintenance.restore(c, folder, out)
    assert active.read_bytes() == b"corrupt synthetic database"
    assert analysis.show(replace(c, data_dir=out), id)["analyses"][0]["current"]


def test_no_overwrite_or_source_overlap(tmp_path):
    c, _ = configured(tmp_path)
    folder = Path(maintenance.backup(c)["directory"])
    with pytest.raises(IndexError):
        maintenance.backup(c, folder)
    with pytest.raises(IndexError):
        maintenance.backup(c, c.source_dirs[0] / "backup")
    with pytest.raises(IndexError):
        maintenance.restore(c, folder, c.data_dir)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "precious").write_text("keep")
    with pytest.raises(IndexError):
        maintenance.restore(c, folder, existing)
    assert (existing / "precious").read_text() == "keep"


def test_maintenance_lock_blocks_writers_but_not_reads(tmp_path):
    c, _ = configured(tmp_path)
    with book_lock(c.data_dir, exclusive=True):
        assert retrieve(c, "search", query="society")["results"]
        with pytest.raises(IndexError):
            with connect(c.data_dir, writable=True):
                pass
        with pytest.raises(IndexError):
            with analysis.database(c, True):
                pass
    with book_lock(c.data_dir):
        with pytest.raises(IndexError):
            maintenance.backup(c)


def test_interrupted_copy_cleans_incomplete_destination(tmp_path, monkeypatch):
    c, _ = configured(tmp_path)
    real = maintenance.write_private

    def fail(path, data):
        if path.name == "manifest.json":
            raise OSError("simulated disk full")
        real(path, data)

    monkeypatch.setattr(maintenance, "write_private", fail)
    out = tmp_path / "backup"
    with pytest.raises(OSError):
        maintenance.backup(c, out)
    assert not out.exists()
    assert retrieve(c, "search", query="society")["results"]


def test_setup_codex_existing_and_symlink_preserved(tmp_path, capsys):
    folder = tmp_path / "book with spaces"
    assert main(["setup", str(folder), "--codex", "--json"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["codex"]["created"]
    text = (folder / "AGENTS.md").read_text()
    assert str(folder / "scholium.toml") in text
    assert "analysis import" in text and "--config" in text and "status --json" in text
    assert main(["setup", str(folder), "--codex", "--json"]) == 0
    assert not json.loads(capsys.readouterr().out)["codex"]["created"]
    (folder / "AGENTS.md").unlink()
    private = tmp_path / "private"
    private.write_text("keep")
    (folder / "AGENTS.md").symlink_to(private)
    assert not integration.codex_setup(folder / "scholium.toml")["created"]
    assert private.read_text() == "keep"


def test_startup_is_generation_only_and_safe_arguments(tmp_path):
    c, _ = configured(tmp_path)
    target = tmp_path / "start book.plist"
    r = integration.startup(c, target)
    assert not r["installed"]
    p = plistlib.loads(target.read_bytes())
    assert p["ProgramArguments"][1:] == ["--config", str(c.path), "watch"]
    assert p["KeepAlive"] is False and p["StandardOutPath"] == "/dev/null"
    with pytest.raises(IndexError):
        integration.startup(c, target)


def test_backup_restore_cli(tmp_path, capsys):
    c, _ = configured(tmp_path)
    base = ["--config", str(c.path)]
    assert main(base + ["backup", "--json"]) == 0
    folder = json.loads(capsys.readouterr().out)["directory"]
    assert main(["backup-check", folder, "--json"]) == 0
    capsys.readouterr()
    assert main(base + ["restore", folder, "--output", str(tmp_path / "restored"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]


def test_schema1_backup_restore_migrates_on_next_write(tmp_path):
    c, _ = configured(tmp_path)
    # Schema 1 predates analysis; this synthetic book has no retained analyses.
    (c.data_dir / "analysis.sqlite3").unlink()
    with sqlite3.connect(c.data_dir / "index.sqlite3") as db:
        db.execute("drop table events")
        db.execute("pragma user_version=1")
    folder = Path(maintenance.backup(c)["directory"])
    assert maintenance.verify(folder)["index"]["schema"] == 1
    out = tmp_path / "restored"
    maintenance.restore(c, folder, out)
    with connect(out, writable=True) as db:
        assert db.execute("pragma user_version").fetchone()[0] == 2
        assert db.execute("select count(*) from revisions").fetchone()[0] == 1
    assert list((out / "backups").glob("schema1-*.sqlite3"))
    assert maintenance.verify(folder)["index"]["schema"] == 1


def test_mismatched_analysis_dependency_rejected(tmp_path):
    c, _ = configured(tmp_path)
    folder = Path(maintenance.backup(c)["directory"])
    target = folder / "analysis.sqlite3"
    with sqlite3.connect(target) as db:
        id, payload = db.execute("select id,payload from analyses").fetchone()
        data = json.loads(payload)
        data["dependencies"][0]["revision"] = "nonexistent"
        db.execute("update analyses set payload=? where id=?", (json.dumps(data), id))
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["files"]["analysis.sqlite3"] = dict(
        bytes=target.stat().st_size, sha256=maintenance.digest(target)
    )
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(IndexError, match="references missing"):
        maintenance.verify(folder)
