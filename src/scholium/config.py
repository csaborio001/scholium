"""Explicit, local configuration; never read manuscript content."""

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib

TEMPLATE = """# scholium book configuration (private: exclude from version control)
schema_version = 1

[manuscript]
# Absolute paths or paths relative to this file. Add folders before ingestion.
source_dirs = [] # e.g. ["manuscript", "/absolute/path/to/chapters"]
languages = ["en", "de"]

[storage]
data_dir = ".scholium"
"""


class ConfigError(ValueError):
    """Actionable configuration error."""


@dataclass(frozen=True)
class Config:
    path: Path
    source_dirs: tuple[Path, ...]
    languages: tuple[str, ...]
    data_dir: Path


def discover(explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    current = Path.cwd()
    for parent in (current, *current.parents):
        candidate = parent / "scholium.toml"
        if candidate.exists():
            return candidate
    return None


def setup(target: str) -> tuple[Path, bool]:
    directory = Path(target).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "scholium.toml"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path, False
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(TEMPLATE)
    return path, True


def load(path: Path) -> Config:
    try:
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(
            "Cannot read configuration; check the path, permissions and TOML syntax."
        ) from exc
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ConfigError("schema_version must be 1.")
    if set(raw) - {"schema_version", "manuscript", "storage"}:
        raise ConfigError("Unknown top-level configuration key.")
    manuscript, storage = raw.get("manuscript"), raw.get("storage")
    if not isinstance(manuscript, dict) or not isinstance(storage, dict):
        raise ConfigError("Configuration needs [manuscript] and [storage] tables.")
    if set(manuscript) - {"source_dirs", "languages"} or set(storage) - {"data_dir"}:
        raise ConfigError("Unknown manuscript or storage configuration key.")
    sources, languages = manuscript.get("source_dirs"), manuscript.get("languages")
    for key, value in (("source_dirs", sources), ("languages", languages)):
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ConfigError(f"{key} must be a list of nonempty strings.")
    if not languages or any(language not in {"en", "de"} for language in languages):
        raise ConfigError('languages must contain "en" and/or "de".')
    data = storage.get("data_dir")
    if not isinstance(data, str) or not data.strip():
        raise ConfigError("data_dir must be a nonempty path string.")

    def resolve(value: str) -> Path:
        return (path.parent / Path(value).expanduser()).resolve()

    source_dirs = tuple(dict.fromkeys(resolve(value) for value in sources))
    data_dir = resolve(data)
    for source in source_dirs:
        if source == data_dir or source in data_dir.parents or data_dir in source.parents:
            raise ConfigError("Source and data directories must not overlap.")
    return Config(path, source_dirs, tuple(languages), data_dir)
