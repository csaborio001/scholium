# Extraction schema 1 — Phase 2 contract

Extraction is standalone; no database, persisted document registry or search exists yet.

The JSON object contains schema_version (1), parser_version, document_id (SHA-256 of resolved source path), chapter (explicit label, default filename stem), source (path, filename, sha256), revision (source SHA-256 plus parser version), generated_at (UTC ISO 8601), warnings (code/message/part/location objects), blocks and notes.

Blocks are ordered paragraphs, including empty paragraphs and table-cell paragraphs. Fields: id (`b000001`), number (1-based), type (paragraph/heading), text (Unicode visible saved text), heading_level (integer or null), headings (ancestor/current heading text), part, location (structural XML path), paragraph_id (Word paraId or null), table_path (ordered table/row/cell index objects), anchors, images and hyperlinks. Note paragraphs use the same structure with IDs prefixed by note key. Note bodies contain id (`footnote:1` or `endnote:1`), type, word_id, text (paragraphs joined by newline), blocks, anchors (incoming references), and order (first reference order or null). Special Word separator notes are excluded.

Anchors contain note_id, block_id, offset (Unicode code points into marker-free text), order (within block). Every reference must resolve; every ordinary note must have at least one reference or extraction fails. Different note types never share an identity. Cross-note references are unsupported and fail explicitly. Literal citation text is retained without bibliographic inference.

Images contain offset, kind (inline/floating), relationship_id, target (package path or external target), external, alt_text and title. Hyperlinks contain start/end text offsets, relationship_id, target and anchor. No links are fetched. No pixel interpretation or inferred caption association occurs. Warnings identify unsupported constructs/fields/exclusions without including manuscript excerpts.

IDs are revision-local. Document identity is path-based only in Phase 2: rename changes it. Phase 3 must introduce a persisted identity registry. Stable citation: chapter + full revision + block ID, with heading context and exact quotation; notes use their typed ID and anchor block. No page numbers.

JSON keys are sorted and UTF-8; all content is deterministic for identical input/label/parser. Only generated_at changes. Markdown embeds the same metadata, block/note IDs, in-place note references, image metadata and warning list. Exports are created together in a new owner-only directory; existing output directories are never replaced. On failure no partial final export directory is published. Source hashes are checked again before publication. Source and output directories must not overlap.

## Parser 0.2.1 additions

Each block includes `formatting`: direct run spans with start/end code-point offsets and properties (`strike`, `dstrike`, `b`, `i`, `highlight`). Explicit false values are retained. These are direct formatting properties, not a complete computed style cascade. Style-defined strike/highlight triggers a warning; full style inheritance/layout is not promised. Markdown labels struck spans explicitly and includes direct formatting metadata. Text and note-anchor offsets remain unchanged.

`note_markers` records automatic self-markers within note bodies, including repeated markers. The normal leading marker is represented by the note identity; any additional marker is shown in Markdown as a self-marker. This differs from an incoming body reference and does not create another note.

OOXML `numId=0` explicitly disables automatic numbering and no longer causes a missing-label warning. Parser version changes distinguish new exports from prior outputs; old exports are retained.
