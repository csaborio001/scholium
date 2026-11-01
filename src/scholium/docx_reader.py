"""Bounded, read-only OOXML extraction. Never execute fields or fetch links."""

from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib

PARSER_VERSION = "0.2.1"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_PART = 32 * 1024 * 1024


def tag(local: str) -> str:
    return f"{{{W}}}{local}"


def local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


class ExtractionError(ValueError):
    """Extraction cannot be accepted; no derivative should be published."""


def source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class Reader:
    def __init__(self, data: bytes):
        try:
            self.zip = zipfile.ZipFile(BytesIO(data))
            infos = self.zip.infolist()
            names = [info.filename for info in infos]
            if len(infos) > 5000 or len(names) != len(set(names)):
                raise ExtractionError("Archive has too many or duplicate entries.")
            if sum(info.file_size for info in infos) > MAX_EXPANDED:
                raise ExtractionError("DOCX expanded size exceeds the safety limit.")
            for info in infos:
                if info.flag_bits & 1 or info.file_size > MAX_PART:
                    raise ExtractionError("Encrypted or oversized DOCX part is unsupported.")
                if info.filename.startswith("/") or ".." in info.filename.split("/"):
                    raise ExtractionError("Unsafe archive entry path.")
        except zipfile.BadZipFile as exc:
            raise ExtractionError("File is not a valid DOCX ZIP archive.") from exc
        self.names = set(names)
        self.warnings: list[dict] = []
        self.styles: dict[str, ET.Element] = {}
        self.relationship_cache: dict[str, dict] = {}
        self.headings: list[tuple[int, str]] = []
        self.references: list[dict] = []

    def warn(self, code: str, message: str, part: str, location: str = "") -> None:
        item = dict(code=code, message=message, part=part, location=location)
        if item not in self.warnings:
            self.warnings.append(item)

    def xml(self, name: str) -> ET.Element:
        if name not in self.names:
            raise ExtractionError(f"Required DOCX part is missing: {name}")
        try:
            data = self.zip.read(name)
            # XML declarations with UTF-16/32 NUL bytes must not bypass DTD checks.
            safe_scan = data.replace(b"\x00", b"").upper()
            if b"<!DOCTYPE" in safe_scan or b"<!ENTITY" in safe_scan:
                raise ExtractionError("DTD/entity declarations are not permitted.")
            return ET.fromstring(data)
        except (
            ET.ParseError,
            zipfile.BadZipFile,
            RuntimeError,
            NotImplementedError,
            zlib.error,
        ) as exc:
            raise ExtractionError(f"Unreadable or malformed XML part: {name}") from exc

    def relationships(self, part: str) -> dict:
        if part in self.relationship_cache:
            return self.relationship_cache[part]
        parent, filename = posixpath.split(part)
        relpath = posixpath.join(parent, "_rels", filename + ".rels") if part else "_rels/.rels"
        result = {}
        if relpath in self.names:
            for element in self.xml(relpath):
                rid = element.get("Id")
                target = element.get("Target", "")
                external = element.get("TargetMode") == "External"
                if not rid or rid in result or not target:
                    raise ExtractionError("Malformed or duplicate OOXML relationship.")
                resolved = (
                    target
                    if external
                    else posixpath.normpath(
                        posixpath.join(parent, target) if not target.startswith("/") else target[1:]
                    )
                )
                if not external and (resolved.startswith("../") or "\\" in resolved):
                    raise ExtractionError("OOXML relationship escapes the package.")
                result[rid] = dict(
                    target=resolved,
                    external=external,
                    type=element.get("Type", "").rsplit("/", 1)[-1],
                )
        self.relationship_cache[part] = result
        return result

    def related(self, part: str, kind: str) -> str | None:
        matches = [rel for rel in self.relationships(part).values() if rel["type"] == kind]
        if len(matches) > 1:
            raise ExtractionError(f"Ambiguous {kind} relationship.")
        if not matches:
            return None
        if matches[0]["external"]:
            raise ExtractionError(f"External {kind} part is unsupported.")
        return matches[0]["target"]

    def inspect(self, root: ET.Element, part: str) -> None:
        for element in root.iter():
            name = local(element)
            if element.tag.startswith("{" + W + "}") and name.endswith("Change"):
                raise ExtractionError(
                    "Tracked property changes are unsupported; use a reviewed copy in Word."
                )
            if element.tag in {
                tag(n)
                for n in (
                    "ins",
                    "del",
                    "moveFrom",
                    "moveTo",
                    "moveFromRangeStart",
                    "moveToRangeStart",
                    "pPrChange",
                    "rPrChange",
                    "tblPrChange",
                    "trPrChange",
                    "tcPrChange",
                    "sectPrChange",
                    "numberingChange",
                    "cellIns",
                    "cellDel",
                    "cellMerge",
                )
            }:
                raise ExtractionError(
                    "Tracked changes are unsupported; use a reviewed copy in Word."
                )
            if name == "altChunk":
                raise ExtractionError("Embedded alternate document content is unsupported.")
            if name in {"commentRangeStart", "commentReference"}:
                self.warn("comments_excluded", "Comment bodies are excluded.", part)
            if name in {"instrText", "fldSimple", "fldChar"}:
                self.warn(
                    "saved_field_result",
                    "Saved field results retained; fields not evaluated.",
                    part,
                )
            if element.tag == tag("numPr"):
                num_id = element.find(tag("numId"))
                # OOXML numId=0 explicitly removes numbering; it is not a lost label.
                if num_id is None or num_id.get(tag("val")) != "0":
                    self.warn(
                        "automatic_numbering", "Automatic list labels are not reconstructed.", part
                    )
            if name in {"vMerge", "gridSpan"}:
                self.warn("merged_table", "Merged table geometry needs manual review.", part)
            if name in {"vanish", "webHidden"}:
                self.warn(
                    "hidden_text", "Stored hidden text is included; review Word visibility.", part
                )
            if name in {"headerReference", "footerReference"}:
                self.warn("headers_footers_excluded", "Headers and footers are excluded.", part)
            if name in {"txbxContent", "object", "pict", "oMath", "oMathPara"}:
                self.warn("unsupported_content", f"Unsupported {name} content excluded.", part)

    def heading_level(self, paragraph: ET.Element) -> int | None:
        properties = paragraph.find(tag("pPr"))
        if properties is None:
            return None
        outline = properties.find(tag("outlineLvl"))
        style = properties.find(tag("pStyle"))
        sid = style.get(tag("val")) if style is not None else None
        seen = set()
        while outline is None and sid and sid not in seen:
            seen.add(sid)
            definition = self.styles.get(sid)
            if definition is None:
                # Built-in style identifiers remain English in many localized documents.
                match = re.fullmatch(r"Heading([1-9])", sid, re.IGNORECASE)
                return int(match[1]) if match else None
            outline = definition.find(f"{tag('pPr')}/{tag('outlineLvl')}")
            base = definition.find(tag("basedOn"))
            sid = base.get(tag("val")) if base is not None else None
        if outline is not None:
            try:
                value = int(outline.get(tag("val"), "9"))
            except ValueError as exc:
                raise ExtractionError("Invalid heading outline level.") from exc
            return value + 1 if 0 <= value <= 8 else None
        return None

    def paragraph(
        self,
        paragraph: ET.Element,
        part: str,
        location: str,
        number: int,
        prefix: str,
        table_path: list,
    ) -> dict:
        block_id = f"{prefix}b{number:06d}"
        pieces: list[str] = []
        anchors, images, hyperlinks = [], [], []
        formatting = []
        note_markers = []
        length = 0

        def append(value: str) -> None:
            nonlocal length
            pieces.append(value)
            length += len(value)

        def visit(element: ET.Element) -> None:
            name = local(element)
            if element.tag == tag("r"):
                start = length
                for child in element:
                    visit(child)
                properties = element.find(tag("rPr"))
                marks = {}
                if properties is not None:
                    for property_name in ("strike", "dstrike", "b", "i"):
                        prop = properties.find(tag(property_name))
                        if prop is not None:
                            marks[property_name] = prop.get(tag("val"), "true") not in {
                                "0",
                                "false",
                                "off",
                            }
                    highlight = properties.find(tag("highlight"))
                    if highlight is not None:
                        marks["highlight"] = highlight.get(tag("val"), "none")
                if marks and length > start:
                    formatting.append(dict(start=start, end=length, properties=marks))
                    if marks.get("strike") or marks.get("dstrike"):
                        self.warn(
                            "struck_text_preserved",
                            "Manually struck text retained and marked; do not treat it as unqualified current prose.",
                            part,
                        )
            elif element.tag == tag("t"):
                append(element.text or "")
            elif element.tag in {tag("tab"), tag("ptab")}:
                append("\t")
            elif element.tag in {tag("br"), tag("cr")}:
                append("\n")
            elif element.tag == tag("noBreakHyphen"):
                append("\u2011")
            elif element.tag == tag("softHyphen"):
                append("\u00ad")
            elif element.tag in {tag("footnoteRef"), tag("endnoteRef")} and prefix:
                note_markers.append(dict(note_id=prefix[:-1], offset=length))
            elif element.tag in {tag("footnoteReference"), tag("endnoteReference")}:
                if prefix:
                    raise ExtractionError("References from within notes are unsupported.")
                kind = "footnote" if name == "footnoteReference" else "endnote"
                word_id = element.get(tag("id"))
                if word_id is None:
                    raise ExtractionError("Note reference lacks an ID.")
                reference = dict(
                    note_id=f"{kind}:{word_id}",
                    block_id=block_id,
                    offset=length,
                    order=len(anchors) + 1,
                )
                anchors.append(reference)
                self.references.append(reference)
                if element.get(tag("customMarkFollows")):
                    self.warn(
                        "custom_note_mark", "Custom note marker requires manual review.", part
                    )
            elif element.tag == tag("drawing"):
                for drawing in element:
                    if drawing.tag not in {f"{{{WP}}}inline", f"{{{WP}}}anchor"}:
                        self.warn(
                            "unsupported_drawing", "Unrecognized drawing container.", part, location
                        )
                        continue
                    props = drawing.find(f"{{{WP}}}docPr")
                    blips = list(drawing.iter(f"{{{A}}}blip"))
                    if not blips:
                        self.warn(
                            "unsupported_drawing",
                            "Drawing has no supported image reference.",
                            part,
                            location,
                        )
                    for blip in blips:
                        rid = blip.get(f"{{{R}}}embed") or blip.get(f"{{{R}}}link")
                        rel = self.relationships(part).get(rid)
                        if rel is None or rel["type"] != "image":
                            raise ExtractionError("Image relationship is missing or invalid.")
                        if not rel["external"] and rel["target"] not in self.names:
                            raise ExtractionError("Referenced image part is missing.")
                        kind = "inline" if local(drawing) == "inline" else "floating"
                        images.append(
                            dict(
                                offset=length,
                                kind=kind,
                                relationship_id=rid,
                                target=rel["target"],
                                external=rel["external"],
                                alt_text=props.get("descr", "") if props is not None else "",
                                title=props.get("title", "") if props is not None else "",
                            )
                        )
                        self.warn(
                            "image_not_interpreted",
                            "Image pixels are not extracted or interpreted.",
                            part,
                        )
                        if kind == "floating":
                            self.warn(
                                "floating_image",
                                "Floating image position needs manual review.",
                                part,
                                location,
                            )
            elif element.tag == tag("hyperlink"):
                start = length
                for child in element:
                    visit(child)
                rid = element.get(f"{{{R}}}id")
                rel = self.relationships(part).get(rid) if rid else None
                if rid and rel is None:
                    raise ExtractionError("Hyperlink relationship is missing.")
                hyperlinks.append(
                    dict(
                        start=start,
                        end=length,
                        relationship_id=rid,
                        target=rel["target"] if rel else None,
                        anchor=element.get(tag("anchor")),
                    )
                )
            elif name == "AlternateContent":
                choices = list(element)
                self.warn(
                    "alternate_content",
                    "First alternate representation used; review fidelity.",
                    part,
                    location,
                )
                if choices:
                    for child in choices[0]:
                        visit(child)
            elif name in {
                "pPr",
                "rPr",
                "instrText",
                "fldChar",
                "footnoteRef",
                "endnoteRef",
                "bookmarkStart",
                "bookmarkEnd",
                "commentRangeStart",
                "commentRangeEnd",
                "commentReference",
                "proofErr",
                "lastRenderedPageBreak",
                "permStart",
                "permEnd",
            }:
                return
            elif name in {"txbxContent", "object", "pict", "oMath", "oMathPara"}:
                return
            elif element.tag == tag("sym"):
                self.warn(
                    "symbol_excluded",
                    "Font-specific symbol omitted; manual review required.",
                    part,
                    location,
                )
            else:
                if name not in {
                    "p",
                    "r",
                    "sdt",
                    "sdtContent",
                    "smartTag",
                    "customXml",
                    "fldSimple",
                    "dir",
                    "bdo",
                }:
                    self.warn(
                        "unhandled_element",
                        f"Unrecognized {name} wrapper; text traversal attempted.",
                        part,
                        location,
                    )
                for child in element:
                    visit(child)

        visit(paragraph)
        text = "".join(pieces)
        level = self.heading_level(paragraph)
        if level and not prefix:
            self.headings = [(n, title) for n, title in self.headings if n < level]
            self.headings.append((level, text))
        return dict(
            id=block_id,
            number=number,
            type="heading" if level else "paragraph",
            text=text,
            heading_level=level,
            headings=[title for _, title in self.headings] if not prefix else [],
            part=part,
            location=location,
            paragraph_id=paragraph.get(f"{{{W14}}}paraId"),
            table_path=table_path,
            formatting=formatting,
            note_markers=note_markers,
            anchors=anchors,
            images=images,
            hyperlinks=hyperlinks,
        )

    def blocks(self, container: ET.Element, part: str, prefix: str = "") -> list[dict]:
        result: list[dict] = []

        def walk(element: ET.Element, location: str, tables: list, table_number: int = 0) -> None:
            counters: dict[str, int] = {}
            for child in element:
                name = local(child)
                counters[name] = counters.get(name, 0) + 1
                path = f"{location}/{name}[{counters[name]}]"
                if child.tag == tag("p"):
                    result.append(
                        self.paragraph(child, part, path, len(result) + 1, prefix, tables)
                    )
                elif child.tag == tag("tbl"):
                    if tables:
                        self.warn(
                            "nested_table",
                            "Nested table order preserved; layout needs review.",
                            part,
                            path,
                        )
                    walk(child, path, tables, counters[name])
                elif child.tag == tag("tr"):
                    walk(
                        child,
                        path,
                        [*tables, {"table": table_number, "row": counters[name], "cell": 0}],
                    )
                elif child.tag == tag("tc"):
                    updated = (
                        [*tables[:-1], {**tables[-1], "cell": counters[name]}] if tables else []
                    )
                    walk(child, path, updated)
                elif name in {"sectPr", "tblPr", "tblGrid", "trPr", "tcPr", "sdtPr", "sdtEndPr"}:
                    continue
                elif name in {"sdt", "sdtContent", "customXml"}:
                    self.warn(
                        "content_wrapper",
                        "Content wrapper flattened in structural order.",
                        part,
                        path,
                    )
                    walk(child, path, tables, table_number)
                else:
                    self.warn(
                        "unsupported_block", f"Unsupported body element {name} omitted.", part, path
                    )

        walk(container, local(container), [])
        return result

    def extract(self) -> tuple[list, list]:
        if "[Content_Types].xml" not in self.names:
            raise ExtractionError("Missing DOCX content types.")
        self.xml("[Content_Types].xml")
        document = self.related("", "officeDocument")
        if not document:
            raise ExtractionError("Missing main document relationship.")
        root = self.xml(document)
        if root.tag != tag("document"):
            raise ExtractionError("Unsupported Word namespace or document root.")
        self.inspect(root, document)
        styles = self.related(document, "styles")
        if styles:
            style_root = self.xml(styles)
            if any(
                e.tag in {tag("strike"), tag("dstrike"), tag("highlight")}
                for e in style_root.iter()
            ):
                self.warn(
                    "inherited_editorial_formatting",
                    "Style-defined strike/highlight detected; only direct run formatting is preserved. Review affected styles before accepting extraction.",
                    styles,
                )
            self.styles = {
                e.get(tag("styleId")): e for e in self.xml(styles) if e.tag == tag("style")
            }
        if self.related(document, "comments"):
            self.warn("comments_excluded", "Comment bodies are excluded.", document)
        body = root.find(tag("body"))
        if body is None:
            raise ExtractionError("Missing document body.")
        blocks = self.blocks(body, document)
        notes = []
        for kind in ("footnote", "endnote"):
            part = self.related(document, kind + "s")
            if part is None:
                continue
            note_root = self.xml(part)
            self.inspect(note_root, part)
            seen = set()
            for element in note_root:
                if element.tag != tag(kind):
                    self.warn(
                        "unsupported_note_element", "Unexpected note container element.", part
                    )
                    continue
                word_id = element.get(tag("id"))
                if word_id is None or word_id in seen:
                    raise ExtractionError("Missing or duplicate note ID.")
                seen.add(word_id)
                if element.get(tag("type"), "normal") in {
                    "separator",
                    "continuationSeparator",
                    "continuationNotice",
                }:
                    continue
                key = f"{kind}:{word_id}"
                note_blocks = self.blocks(element, part, prefix=key + ":")
                incoming = [ref for ref in self.references if ref["note_id"] == key]
                if not incoming:
                    raise ExtractionError(
                        "Unreferenced ordinary note found; manual review required."
                    )
                notes.append(
                    dict(
                        id=key,
                        type=kind,
                        word_id=word_id,
                        text="\n".join(block["text"] for block in note_blocks),
                        blocks=note_blocks,
                        anchors=incoming,
                        order=self.references.index(incoming[0]) + 1,
                    )
                )
        keys = {note["id"] for note in notes}
        if any(reference["note_id"] not in keys for reference in self.references):
            raise ExtractionError("A note marker has no matching note body.")
        return blocks, sorted(notes, key=lambda note: note["order"])


def extract(path: Path, chapter: str | None = None, generated_at: str | None = None) -> dict:
    path = path.expanduser().resolve()
    if path.suffix.lower() != ".docx" or path.name.startswith("~$"):
        raise ExtractionError("Select a DOCX chapter, not a Word lock file or legacy DOC.")
    with path.open("rb") as stream:
        data = stream.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ExtractionError("DOCX exceeds the 128 MiB input limit.")
    digest = hashlib.sha256(data).hexdigest()
    reader = Reader(data)
    try:
        blocks, notes = reader.extract()
    except RecursionError as exc:
        raise ExtractionError("XML nesting exceeds the supported depth.") from exc
    finally:
        reader.zip.close()
    if source_hash(path) != digest:
        raise ExtractionError("Source changed during extraction; retry after Word finishes saving.")
    return dict(
        schema_version=1,
        parser_version=PARSER_VERSION,
        document_id=hashlib.sha256(str(path).encode()).hexdigest(),
        chapter=chapter or path.stem,
        source=dict(path=str(path), filename=path.name, sha256=digest),
        revision=f"{digest}:{PARSER_VERSION}",
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        warnings=reader.warnings,
        blocks=blocks,
        notes=notes,
    )
