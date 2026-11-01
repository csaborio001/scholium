import hashlib
import json
import zipfile

import pytest

from scholium.cli import main
from scholium.docx_reader import ExtractionError, W, extract
from scholium.render import json_text, markdown, publish

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def relationships(items):
    return (
        f'<Relationships xmlns="{REL}">'
        + "".join(
            f'<Relationship Id="{rid}" Type="{R}/{kind}" Target="{target}" {extra}/>'
            for rid, kind, target, extra in items
        )
        + "</Relationships>"
    )


def fixture(path, body=None, footnotes=None, endnotes=None, extra=None):
    if body is None:
        body = """<w:p w14:paraId="ABCD"><w:pPr><w:pStyle w:val="CustomHeading"/></w:pPr><w:r><w:t>Einführung</w:t></w:r></w:p>
<w:p><w:r><w:t xml:space="preserve">Größe und </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>ideas</w:t><w:footnoteReference w:id="1"/><w:t> — </w:t><w:endnoteReference w:id="1"/><w:footnoteReference w:id="1"/></w:r></w:p>
<w:p/>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell one</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Cell two</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><w:hyperlink r:id="link"><w:r><w:t>Visible link</w:t></w:r></w:hyperlink><w:fldSimple w:instr="SEQ Figure"><w:r><w:t>1</w:t></w:r></w:fldSimple><w:r><w:t>: Caption</w:t></w:r></w:p>
<w:p><w:r><w:drawing><wp:inline><wp:docPr id="1" name="image" descr="Historical map" title="Map"/><a:graphic><a:graphicData><a:blip r:embed="image"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"""
    if footnotes is None:
        footnotes = '<w:footnote w:type="separator" w:id="-1"><w:p/></w:footnote><w:footnote w:id="1"><w:p><w:r><w:footnoteRef/><w:t>Fußnote: Müller (1900).</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p></w:footnote>'
    if endnotes is None:
        endnotes = '<w:endnote w:id="1"><w:p><w:r><w:endnoteRef/><w:t>Endnote evidence.</w:t></w:r></w:p></w:endnote>'
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "_rels/.rels": relationships([("doc", "officeDocument", "word/document.xml", "")]),
        "word/_rels/document.xml.rels": relationships(
            [
                ("fn", "footnotes", "footnotes.xml", ""),
                ("en", "endnotes", "endnotes.xml", ""),
                ("st", "styles", "styles.xml", ""),
                ("image", "image", "media/image.png", ""),
                ("link", "hyperlink", "https://example.invalid/", 'TargetMode="External"'),
            ]
        ),
        "word/document.xml": f'<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><w:body>{body}</w:body></w:document>',
        "word/styles.xml": f'<w:styles xmlns:w="{W}"><w:style w:styleId="CustomHeading"><w:basedOn w:val="Heading1"/></w:style><w:style w:styleId="Heading1"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>',
        "word/footnotes.xml": f'<w:footnotes xmlns:w="{W}">{footnotes}</w:footnotes>',
        "word/endnotes.xml": f'<w:endnotes xmlns:w="{W}">{endnotes}</w:endnotes>',
        "word/media/image.png": b"synthetic-image-placeholder",
    }
    parts.update(extra or {})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return path


def test_fidelity_and_revision_links(tmp_path):
    path = fixture(tmp_path / "chapter.docx")
    before = path.read_bytes()
    doc = extract(path, "CH01", generated_at="2026-10-30T00:00:00+00:00")
    assert [b["text"] for b in doc["blocks"]] == [
        "Einführung",
        "Größe und ideas — ",
        "",
        "Cell one",
        "Cell two",
        "Visible link1: Caption",
        "",
    ]
    assert doc["blocks"][0]["heading_level"] == 1
    assert doc["blocks"][0]["paragraph_id"] == "ABCD"
    assert doc["blocks"][1]["headings"] == ["Einführung"]
    assert [(a["note_id"], a["offset"]) for a in doc["blocks"][1]["anchors"]] == [
        ("footnote:1", 15),
        ("endnote:1", 18),
        ("footnote:1", 18),
    ]
    assert doc["notes"][0]["text"] == "Fußnote: Müller (1900).\nSecond paragraph."
    assert len(doc["notes"][0]["anchors"]) == 2
    assert doc["notes"][1]["id"] == "endnote:1"
    assert doc["blocks"][4]["table_path"] == [{"table": 1, "row": 1, "cell": 2}]
    assert doc["blocks"][5]["hyperlinks"][0]["target"] == "https://example.invalid/"
    assert doc["blocks"][6]["images"][0]["alt_text"] == "Historical map"
    assert doc["source"]["sha256"] == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before
    assert json_text(doc) == json_text(extract(path, "CH01", generated_at=doc["generated_at"]))
    assert "ideas[footnote:1] — [endnote:1][footnote:1]" in markdown(doc)


def test_export_pair_private_and_non_overwriting(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    path = fixture(source / "chapter.docx")
    doc = extract(path)
    out = publish(doc, tmp_path / "output")
    assert out.stat().st_mode & 0o777 == 0o700
    assert (out / "chapter.json").stat().st_mode & 0o777 == 0o600
    assert json.loads((out / "chapter.json").read_text()) == doc
    with pytest.raises(ExtractionError, match="already exists"):
        publish(doc, out)
    with pytest.raises(ExtractionError, match="overlap"):
        publish(doc, source / "output")


def test_changed_source_prevents_publication(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    path = fixture(source / "chapter.docx")
    doc = extract(path)
    path.write_bytes(b"changed")
    with pytest.raises(ExtractionError, match="changed"):
        publish(doc, tmp_path / "output")
    assert not (tmp_path / "output").exists()
    assert not list(tmp_path.glob(".scholium-export-*"))
    assert not list(tmp_path.glob("*.scholium-lock"))


@pytest.mark.parametrize(
    "body,fn,en,message",
    [
        ("<w:p><w:ins><w:r><w:t>change</w:t></w:r></w:ins></w:p>", "", "", "Tracked changes"),
        ('<w:p><w:r><w:endnoteReference w:id="9"/></w:r></w:p>', "", "", "no matching"),
        ("<w:p/>", '<w:footnote w:id="1"><w:p/></w:footnote>', "", "Unreferenced"),
        (
            '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>',
            '<w:footnote w:id="1"><w:p/></w:footnote><w:footnote w:id="1"><w:p/></w:footnote>',
            "",
            "duplicate",
        ),
        ("<w:altChunk/>", "", "", "alternate"),
    ],
)
def test_rejected_content(tmp_path, body, fn, en, message):
    path = fixture(tmp_path / "bad.docx", body, fn, en)
    with pytest.raises(ExtractionError, match=message):
        extract(path)


def test_warnings_and_tabs_breaks(tmp_path):
    body = '<w:p><w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/><w:t>C</w:t><w:noBreakHyphen/><w:softHyphen/></w:r><w:commentReference w:id="0"/><w:r><w:pict/></w:r></w:p><w:sectPr><w:headerReference/></w:sectPr>'
    doc = extract(fixture(tmp_path / "warnings.docx", body, "", ""))
    assert doc["blocks"][0]["text"] == "A\tB\nC\u2011\u00ad"
    assert {"comments_excluded", "unsupported_content", "headers_footers_excluded"} <= {
        w["code"] for w in doc["warnings"]
    }


@pytest.mark.parametrize("payload", [b"not a zip", b"PK\x03\x04"])
def test_invalid_zip(tmp_path, payload):
    path = tmp_path / "bad.docx"
    path.write_bytes(payload)
    with pytest.raises(ExtractionError, match="ZIP"):
        extract(path)


def test_xml_entity_rejected_in_utf16(tmp_path):
    xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY x "bad">]><x>&x;</x>'
    path = fixture(tmp_path / "bad.docx", extra={"word/document.xml": xml.encode("utf-16")})
    with pytest.raises(ExtractionError, match="DTD"):
        extract(path)


def test_malformed_xml(tmp_path):
    path = fixture(tmp_path / "bad.docx", extra={"word/document.xml": "<broken"})
    with pytest.raises(ExtractionError, match="malformed"):
        extract(path)


def test_cli_extract_and_failure(tmp_path, capsys):
    source = tmp_path / "source"
    source.mkdir()
    path = fixture(source / "chapter.docx")
    assert main(["extract", str(path), "--output", str(tmp_path / "export"), "--json"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["notes"] == 2
    assert "Größe" not in json.dumps(response)
    assert main(["extract", str(path), "--output", str(tmp_path / "export"), "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_archive_limits(tmp_path, monkeypatch):
    import scholium.docx_reader as reader

    path = fixture(tmp_path / "chapter.docx")
    monkeypatch.setattr(reader, "MAX_PART", 10)
    with pytest.raises(ExtractionError, match="oversized"):
        extract(path)


def test_markdown_fence_safety(tmp_path):
    doc = extract(
        fixture(
            tmp_path / "chapter.docx", "<w:p><w:r><w:t>```\n# content</w:t></w:r></w:p>", "", ""
        )
    )
    assert "````text\n```\n# content\n````" in markdown(doc)


def test_note_table_and_heading_hierarchy(tmp_path):
    body = '<w:p><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:r><w:t>First</w:t></w:r></w:p><w:p><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:r><w:t>Second</w:t><w:endnoteReference w:id="2"/></w:r></w:p>'
    notes = '<w:endnote w:id="2"><w:tbl><w:tr><w:tc><w:p><w:r><w:t>In table</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:endnote>'
    doc = extract(fixture(tmp_path / "chapter.docx", body, "", notes))
    assert doc["blocks"][1]["headings"] == ["First", "Second"]
    assert doc["notes"][0]["text"] == "In table"
    assert doc["notes"][0]["blocks"][0]["table_path"][0]["cell"] == 1


def test_missing_image_relationship(tmp_path):
    from scholium.docx_reader import R, WP, A

    body = f'<w:p><w:r><w:drawing><wp:inline xmlns:wp="{WP}" xmlns:a="{A}" xmlns:r="{R}"><a:blip r:embed="missing"/></wp:inline></w:drawing></w:r></w:p>'
    with pytest.raises(ExtractionError, match="Image relationship"):
        extract(fixture(tmp_path / "chapter.docx", body, "", ""))


def test_failed_render_leaves_no_partial_export(tmp_path, monkeypatch):
    import scholium.render as render

    source = tmp_path / "source"
    source.mkdir()
    doc = extract(fixture(source / "chapter.docx"))

    def fail(_):
        raise OSError("synthetic disk error")

    monkeypatch.setattr(render, "markdown", fail)
    with pytest.raises(OSError):
        publish(doc, tmp_path / "output")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["source"]


def test_golden_exports(tmp_path):
    from pathlib import Path

    doc = extract(
        fixture(
            tmp_path / "simple.docx", "<w:p><w:r><w:t>English und Größe.</w:t></w:r></w:p>", "", ""
        ),
        "CH01",
        "2026-10-30T00:00:00+00:00",
    )
    doc["document_id"] = "DOCUMENT_ID"
    doc["source"] = {
        "path": "/synthetic/simple.docx",
        "filename": "simple.docx",
        "sha256": "SOURCE_HASH",
    }
    doc["revision"] = "SOURCE_HASH:0.2.1"
    golden = Path(__file__).parent / "fixtures"
    assert json_text(doc) == (golden / "simple.json").read_text()
    assert markdown(doc) == (golden / "simple.md").read_text()


@pytest.mark.parametrize("num_id, warns", [("0", False), ("1", True)])
def test_explicitly_disabled_numbering_is_not_missing_content(tmp_path, num_id, warns):
    body = f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr></w:pPr><w:r><w:t>Text</w:t></w:r></w:p>'
    doc = extract(fixture(tmp_path / "chapter.docx", body, "", ""))
    assert any(w["code"] == "automatic_numbering" for w in doc["warnings"]) is warns


def test_strike_and_highlight_survive_without_changing_text_or_offsets(tmp_path):
    body = '<w:p><w:r><w:rPr><w:strike/><w:highlight w:val="yellow"/></w:rPr><w:t>Draft</w:t><w:endnoteReference w:id="1"/></w:r><w:r><w:rPr><w:strike w:val="0"/></w:rPr><w:t> current</w:t></w:r></w:p>'
    notes = '<w:endnote w:id="1"><w:p><w:r><w:t>Note</w:t></w:r></w:p></w:endnote>'
    doc = extract(fixture(tmp_path / "chapter.docx", body, "", notes))
    block = doc["blocks"][0]
    assert block["text"] == "Draft current"
    assert block["anchors"][0]["offset"] == 5
    assert block["formatting"][0] == {
        "start": 0,
        "end": 5,
        "properties": {"strike": True, "highlight": "yellow"},
    }
    assert block["formatting"][1]["properties"]["strike"] is False
    assert "[STRIKETHROUGH]Draft[/STRIKETHROUGH][endnote:1] current" in markdown(doc)
    assert "struck_text_preserved" in {w["code"] for w in doc["warnings"]}


def test_repeated_note_body_self_marker_is_preserved(tmp_path):
    body = '<w:p><w:r><w:endnoteReference w:id="1"/></w:r></w:p>'
    notes = '<w:endnote w:id="1"><w:p><w:r><w:endnoteRef/><w:t>First.</w:t><w:endnoteRef/><w:t> Last.</w:t></w:r></w:p></w:endnote>'
    doc = extract(fixture(tmp_path / "chapter.docx", body, "", notes))
    assert doc["notes"][0]["blocks"][0]["note_markers"] == [
        {"note_id": "endnote:1", "offset": 0},
        {"note_id": "endnote:1", "offset": 6},
    ]
    assert "First.[endnote:1 self-marker] Last." in markdown(doc)
