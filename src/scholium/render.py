"""Traceable exports published only after both files are complete."""

import json
import os
import re
from pathlib import Path
import shutil
import tempfile

from .docx_reader import ExtractionError, source_hash


def json_text(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def fenced(text: str) -> str:
    # A manuscript cannot terminate its own fenced passage.
    fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    return f"{fence}text\n{text}\n{fence}"


def markdown(document: dict) -> str:
    lines = [
        "# scholium extraction",
        "",
        "Machine-generated derivative; do not edit.",
        "",
        fenced(
            json.dumps(
                {
                    key: document[key]
                    for key in (
                        "chapter",
                        "source",
                        "revision",
                        "parser_version",
                        "schema_version",
                        "generated_at",
                    )
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        ),
        "",
        "## Extraction warnings",
        "",
    ]
    lines.extend(
        f"- {w['code']}: {w['message']} ({w['part']} {w['location']})" for w in document["warnings"]
    )
    if not document["warnings"]:
        lines.append("None detected; manual fidelity review is still required.")

    def block_lines(block: dict) -> list[str]:
        text = block["text"]
        insertions = {}
        for anchor in block["anchors"]:
            insertions.setdefault(anchor["offset"], []).append((1, f"[{anchor['note_id']}]"))
        for index, marker in enumerate(block.get("note_markers", [])):
            if not (block["number"] == 1 and index == 0 and marker["offset"] == 0):
                insertions.setdefault(marker["offset"], []).append(
                    (1, f"[{marker['note_id']} self-marker]")
                )
        for span in block.get("formatting", []):
            properties = span["properties"]
            if properties.get("strike") or properties.get("dstrike"):
                insertions.setdefault(span["start"], []).append((2, "[STRIKETHROUGH]"))
                insertions.setdefault(span["end"], []).append((0, "[/STRIKETHROUGH]"))
        for offset in sorted(insertions, reverse=True):
            labels = "".join(
                label for _, label in sorted(insertions[offset], key=lambda item: item[0])
            )
            text = text[:offset] + labels + text[offset:]
        result = [f"### {block['id']}", "", fenced(text), ""]
        metadata = {
            key: block[key]
            for key in (
                "headings",
                "part",
                "location",
                "table_path",
                "images",
                "hyperlinks",
                "formatting",
            )
        }
        result.extend(
            [
                "Location and relationships:",
                fenced(json.dumps(metadata, ensure_ascii=False, sort_keys=True)),
                "",
            ]
        )
        return result

    lines.extend(["", "## Document blocks", ""])
    for block in document["blocks"]:
        lines.extend(block_lines(block))
    lines.extend(["## Notes", ""])
    for note in document["notes"]:
        lines.extend(
            [
                f"### {note['id']}",
                "",
                "Anchors: "
                + ", ".join(f"{a['block_id']} at offset {a['offset']}" for a in note["anchors"]),
                "",
            ]
        )
        for block in note["blocks"]:
            lines.extend(block_lines(block))
    return "\n".join(lines) + "\n"


def publish(document: dict, output: Path) -> Path:
    source = Path(document["source"]["path"]).resolve()
    output = output.expanduser().resolve()
    # A whole new directory is the publication unit; never replace prior results.
    if output == source.parent or source.parent in output.parents or output in source.parents:
        raise ExtractionError("Output and source directories must not overlap.")
    if output.exists():
        raise ExtractionError("Output already exists; choose a new output directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / f".{output.name}.scholium-lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ExtractionError(
            "Output is locked by another extraction; choose another directory."
        ) from exc
    os.close(fd)
    temporary = None
    try:
        temporary = Path(tempfile.mkdtemp(prefix=".scholium-export-", dir=output.parent))
        for name, content in (
            ("chapter.json", json_text(document)),
            ("chapter.md", markdown(document)),
        ):
            file = temporary / name
            with file.open("x", encoding="utf-8") as stream:
                os.chmod(file, 0o600)
                stream.write(content)
        if source_hash(source) != document["source"]["sha256"]:
            raise ExtractionError("Source changed before publication; retry extraction.")
        if output.exists():
            raise ExtractionError("Output appeared during extraction; nothing overwritten.")
        temporary.rename(output)
        temporary = None
        return output
    finally:
        if temporary is not None:
            shutil.rmtree(temporary)
        lock.unlink()
