import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scholium.cli import main
from scholium.config import ConfigError, TEMPLATE, discover, load, setup


def test_setup_preserves_existing_and_permissions(tmp_path):
    path, created = setup(str(tmp_path / "book"))
    assert created
    assert path.stat().st_mode & 0o777 == 0o600
    path.write_text("private existing settings")
    assert setup(str(path.parent)) == (path, False)
    assert path.read_text() == "private existing settings"
    assert list(path.parent.iterdir()) == [path]


def test_setup_does_not_follow_existing_symlink(tmp_path):
    private = tmp_path / "private"
    private.write_text("untouched")
    (tmp_path / "scholium.toml").symlink_to(private)
    assert setup(str(tmp_path))[1] is False
    assert private.read_text() == "untouched"


def test_discovery_and_relative_paths(tmp_path, monkeypatch):
    path, _ = setup(str(tmp_path))
    path.write_text(TEMPLATE.replace("source_dirs = []", 'source_dirs = ["chapters", "other"]'))
    child = tmp_path / "nested"
    child.mkdir()
    monkeypatch.chdir(child)
    assert discover() == path
    config = load(discover())
    assert config.source_dirs == (tmp_path / "chapters", tmp_path / "other")
    assert config.data_dir == tmp_path / ".scholium"
    inner, _ = setup(str(child))
    assert discover() == inner
    assert discover(str(path)) == path


@pytest.mark.parametrize(
    "replacement",
    [
        ("schema_version = 1", "schema_version = true"),
        ("source_dirs = []", 'source_dirs = "bad"'),
        ('languages = ["en", "de"]', 'languages = ["fr"]'),
        ('data_dir = ".scholium"', "data_dir = 1"),
        ("source_dirs = []", "source_dir = []"),
        ("source_dirs = []", 'source_dirs = ["."]'),
        ("source_dirs = []", 'source_dirs = [".scholium/source"]'),
    ],
)
def test_reject_invalid_configuration(tmp_path, replacement):
    path, _ = setup(str(tmp_path))
    path.write_text(TEMPLATE.replace(*replacement))
    with pytest.raises(ConfigError):
        load(path)


def test_malformed_configuration_does_not_echo_content(tmp_path):
    path = tmp_path / "scholium.toml"
    path.write_text("PRIVATE MANUSCRIPT TEXT invalid toml")
    with pytest.raises(ConfigError) as error:
        load(path)
    assert "PRIVATE" not in str(error.value)


def test_doctor_status_and_read_only(tmp_path, capsys):
    path, _ = setup(str(tmp_path))
    assert main(["--config", str(path), "doctor", "--json"]) == 1
    assert not json.loads(capsys.readouterr().out)["ok"]
    source = tmp_path / "chapters"
    source.mkdir()
    document = source / "test.docx"
    document.write_bytes(b"private synthetic bytes: not a real docx")
    path.write_text(TEMPLATE.replace("source_dirs = []", 'source_dirs = ["chapters"]'))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["--config", str(path), "doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert not (tmp_path / ".scholium").exists()


def test_installed_command_from_other_directory(tmp_path):
    executable = Path(sys.executable).parent / "scholium"
    env = {**os.environ, "PATH": f"{executable.parent}:{os.environ['PATH']}"}
    for args in (["--help"], ["setup", ".", "--json"]):
        result = subprocess.run(
            ["scholium", *args], cwd=tmp_path, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["created"]
    result = subprocess.run(
        ["scholium", "--config", str(tmp_path / "missing"), "doctor", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert not json.loads(result.stdout)["ok"]
