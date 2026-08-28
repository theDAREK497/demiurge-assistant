from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from worldbuilder_core.models import DocumentChunkLink, KnowledgeChunk, KnowledgeDocument
from worldbuilder_core.schemas import KnowledgeDocumentProcessResult, KnowledgeDocumentRead

TARGET_CHARS = 4_000
OVERLAP_CHARS = 400
MAX_DOCX_XML_BYTES = 200 * 1024 * 1024
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NEAR_DUPLICATE_PUNCTUATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2026": "...",
    }
)


class DocumentIngestionError(Exception):
    pass


class UnsupportedDocumentError(DocumentIngestionError):
    pass


class InvalidDocumentError(DocumentIngestionError):
    pass


def safe_filename(value: str) -> str:
    filename = Path(value).name.strip()
    if not filename or filename in {".", ".."} or len(filename) > 255:
        raise InvalidDocumentError("Invalid filename")
    if Path(filename).suffix.lower() not in {".txt", ".docx"}:
        raise UnsupportedDocumentError("Only .txt and .docx documents are supported")
    return filename


def create_manifest(document: KnowledgeDocument) -> None:
    source_path = Path(document.storage_path)
    manifest_path = source_path.with_suffix(source_path.suffix + ".chunks.jsonl")
    paragraphs = _read_paragraphs(source_path)
    total_chars = 0
    total_chunks = 0
    with manifest_path.open("w", encoding="utf-8", newline="\n") as output:
        for position, chunk in enumerate(_chunk_paragraphs(paragraphs)):
            total_chars += len(chunk)
            output.write(json.dumps({"position": position, "heading": None, "content": chunk}, ensure_ascii=False))
            output.write("\n")
            total_chunks += 1
    if not total_chunks:
        manifest_path.unlink(missing_ok=True)
        raise InvalidDocumentError("Document contains no readable text")
    document.manifest_path = str(manifest_path)
    document.total_chars = total_chars
    document.total_chunks = total_chunks
    document.status = "chunking"
    document.error = None


def process_document(
    session: Session,
    document: KnowledgeDocument,
    *,
    batch_size: int = 50,
) -> KnowledgeDocumentProcessResult:
    if document.status == "paused":
        raise DocumentIngestionError("Document processing is paused")
    if document.status == "ready":
        return _process_result(document, 0, 0, 0)

    try:
        if not document.manifest_path:
            create_manifest(document)
            session.commit()
        created = 0
        duplicates = 0
        processed = 0
        for record in _manifest_records(Path(document.manifest_path), start=document.processed_chunks):
            chunk, was_duplicate = _get_or_create_chunk(session, document.world_id, record["content"])
            session.add(
                DocumentChunkLink(
                    document_id=document.id,
                    chunk_id=chunk.id,
                    position=record["position"],
                    heading=record.get("heading"),
                )
            )
            document.processed_chunks += 1
            processed += 1
            if was_duplicate:
                document.duplicate_chunks += 1
                duplicates += 1
            else:
                created += 1
            if processed >= batch_size:
                break

        if document.processed_chunks >= document.total_chunks:
            document.status = "ready"
        session.commit()
        session.refresh(document)
        return _process_result(document, processed, created, duplicates)
    except (OSError, ValueError, BadZipFile, ElementTree.ParseError, DocumentIngestionError) as exc:
        session.rollback()
        stored = session.get(KnowledgeDocument, document.id)
        if stored is not None:
            stored.status = "failed"
            stored.error = str(exc)[:2_000]
            session.commit()
        raise InvalidDocumentError(str(exc)) from exc


def pause_document(session: Session, document: KnowledgeDocument) -> KnowledgeDocument:
    if document.status in {"uploaded", "chunking"}:
        document.status = "paused"
        session.commit()
        session.refresh(document)
    return document


def resume_document(session: Session, document: KnowledgeDocument) -> KnowledgeDocument:
    if document.status in {"paused", "failed"}:
        document.status = "chunking" if document.manifest_path else "uploaded"
        document.error = None
        session.commit()
        session.refresh(document)
    return document


def delete_document(session: Session, document: KnowledgeDocument) -> None:
    paths = [Path(document.storage_path)]
    if document.manifest_path:
        paths.append(Path(document.manifest_path))
    world_id = document.world_id
    session.delete(document)
    session.flush()
    orphan_ids = session.scalars(
        select(KnowledgeChunk.id)
        .where(KnowledgeChunk.world_id == world_id)
        .where(~KnowledgeChunk.document_links.any())
    ).all()
    if orphan_ids:
        session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.id.in_(orphan_ids)))
    session.commit()
    for path in paths:
        path.unlink(missing_ok=True)


def world_document_paths(session: Session, world_id: str) -> set[Path]:
    paths: set[Path] = set()
    for storage_path, manifest_path in session.execute(
        select(KnowledgeDocument.storage_path, KnowledgeDocument.manifest_path).where(
            KnowledgeDocument.world_id == world_id
        )
    ):
        paths.add(Path(storage_path))
        if manifest_path:
            paths.add(Path(manifest_path))
    return paths


def cleanup_document_paths(paths: set[Path]) -> None:
    parent_directories = {path.parent for path in paths}
    for path in paths:
        path.unlink(missing_ok=True)
    for directory in sorted(parent_directories, key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _process_result(
    document: KnowledgeDocument,
    processed: int,
    created: int,
    duplicates: int,
) -> KnowledgeDocumentProcessResult:
    return KnowledgeDocumentProcessResult(
        document=KnowledgeDocumentRead.model_validate(document),
        processed_in_batch=processed,
        created_in_batch=created,
        duplicates_in_batch=duplicates,
    )


def _read_paragraphs(path: Path) -> Iterator[str]:
    if path.suffix.lower() == ".txt":
        yield from _read_text(path)
        return
    yield from _read_docx(path)


def _read_text(path: Path) -> Iterator[str]:
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise InvalidDocumentError("Could not decode text document")
    yield from _normalized_paragraphs(text)


def _read_docx(path: Path) -> Iterator[str]:
    try:
        with ZipFile(path) as archive:
            try:
                info = archive.getinfo("word/document.xml")
            except KeyError as exc:
                raise InvalidDocumentError("DOCX has no word/document.xml") from exc
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise InvalidDocumentError("DOCX document XML is too large")
            with archive.open(info) as source:
                table_depth = 0
                table_rows: list[list[str]] = []
                for event, element in ElementTree.iterparse(source, events=("start", "end")):
                    if event == "start" and element.tag == f"{WORD_NS}tbl":
                        table_depth += 1
                        if table_depth == 1:
                            table_rows = []
                        continue
                    if event != "end":
                        continue
                    if element.tag == f"{WORD_NS}p":
                        if table_depth == 0:
                            value = _word_element_text(element)
                            element.clear()
                            if value:
                                yield value
                        continue
                    if element.tag == f"{WORD_NS}tr" and table_depth == 1:
                        row = [_word_element_text(cell) for cell in element.findall(f"{WORD_NS}tc")]
                        if any(row):
                            table_rows.append(row)
                        element.clear()
                        continue
                    if element.tag == f"{WORD_NS}tbl":
                        table_depth -= 1
                        if table_depth == 0:
                            value = _render_document_table(table_rows)
                            element.clear()
                            if value:
                                yield value
    except BadZipFile as exc:
        raise InvalidDocumentError("Invalid DOCX archive") from exc


def _word_element_text(element: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in element.iter():
        if node.tag == f"{WORD_NS}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{WORD_NS}tab":
            parts.append("\t")
        elif node.tag in {f"{WORD_NS}br", f"{WORD_NS}cr"}:
            parts.append("\n")
    return _normalize_text("".join(parts))


def _render_document_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in rows]

    def markdown_row(row: list[str]) -> str:
        cells = [cell.replace("|", "\\|").replace("\n", "<br>") for cell in row]
        return f"| {' | '.join(cells)} |"

    lines = ["[DOCUMENT TABLE]", markdown_row(normalized_rows[0])]
    lines.append(f"| {' | '.join('---' for _ in range(width))} |")
    lines.extend(markdown_row(row) for row in normalized_rows[1:])
    lines.append("[/DOCUMENT TABLE]")
    return "\n".join(lines)


def _normalized_paragraphs(text: str) -> Iterator[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for value in re.split(r"\n\s*\n", normalized):
        value = _normalize_text(value)
        if value:
            yield value


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _chunk_paragraphs(paragraphs: Iterator[str]) -> Iterator[str]:
    current = ""
    for paragraph in paragraphs:
        for part in _split_long_text(paragraph, TARGET_CHARS):
            candidate = f"{current}\n\n{part}".strip() if current else part
            if current and len(candidate) > TARGET_CHARS:
                yield current
                overlap = _tail_overlap_at_boundary(current, OVERLAP_CHARS)
                current = f"{overlap}\n\n{part}".strip()
            else:
                current = candidate
    if current:
        yield current


def _tail_overlap_at_boundary(value: str, limit: int) -> str:
    start = max(0, len(value) - limit)
    if start == 0:
        return value.strip()
    tail = value[start:]
    if tail and not value[start - 1].isspace() and not tail[0].isspace():
        boundary = re.search(r"\s+", tail)
        if boundary is None:
            return ""
        tail = tail[boundary.end() :]
    return tail.lstrip()


def _split_long_text(value: str, limit: int) -> Iterator[str]:
    remaining = value.strip()
    while len(remaining) > limit:
        split_at = max(remaining.rfind(". ", 0, limit), remaining.rfind(" ", 0, limit))
        if split_at < limit // 2:
            split_at = limit
        else:
            split_at += 1
        yield remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()
    if remaining:
        yield remaining


def _manifest_records(path: Path, *, start: int) -> Iterator[dict]:
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source):
            if line_number < start:
                continue
            yield json.loads(line)


def _get_or_create_chunk(session: Session, world_id: str, content: str) -> tuple[KnowledgeChunk, bool]:
    normalized = _normalized_chunk_content(content)
    content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    existing = session.scalar(
        select(KnowledgeChunk).where(
            KnowledgeChunk.world_id == world_id,
            KnowledgeChunk.content_hash == content_hash,
        )
    )
    if existing is not None:
        return existing, True

    fingerprint = _simhash(normalized)
    bands = _fingerprint_bands(fingerprint)
    candidates = session.scalars(
        select(KnowledgeChunk).where(
            KnowledgeChunk.world_id == world_id,
            or_(
                KnowledgeChunk.fingerprint_band_0 == bands[0],
                KnowledgeChunk.fingerprint_band_1 == bands[1],
                KnowledgeChunk.fingerprint_band_2 == bands[2],
                KnowledgeChunk.fingerprint_band_3 == bands[3],
            ),
        )
    )
    for candidate in candidates:
        if (
            (int(candidate.fingerprint, 16) ^ fingerprint).bit_count() <= 3
            and _is_safe_near_duplicate(candidate.content, content)
        ):
            return candidate, True

    fingerprint_hex = f"{fingerprint:016x}"
    chunk = KnowledgeChunk(
        world_id=world_id,
        content_hash=content_hash,
        fingerprint=fingerprint_hex,
        fingerprint_band_0=bands[0],
        fingerprint_band_1=bands[1],
        fingerprint_band_2=bands[2],
        fingerprint_band_3=bands[3],
        content=content,
        char_count=len(content),
    )
    session.add(chunk)
    session.flush()
    return chunk, False


def _normalized_chunk_content(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _is_safe_near_duplicate(left: str, right: str) -> bool:
    """Deduplicate typographic variants without erasing meaningful punctuation."""
    left_normalized = _normalized_chunk_content(left).translate(NEAR_DUPLICATE_PUNCTUATION)
    right_normalized = _normalized_chunk_content(right).translate(NEAR_DUPLICATE_PUNCTUATION)
    return bool(left_normalized) and left_normalized == right_normalized


def _simhash(value: str) -> int:
    tokens = re.findall(r"\w+", value, flags=re.UNICODE)
    features = tokens if len(tokens) < 3 else [" ".join(tokens[index : index + 3]) for index in range(len(tokens) - 2)]
    weights = [0] * 64
    for feature in features:
        digest = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if digest & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            result |= 1 << bit
    return result


def _fingerprint_bands(fingerprint: int) -> tuple[str, str, str, str]:
    return tuple(f"{(fingerprint >> (index * 16)) & 0xFFFF:04x}" for index in range(4))  # type: ignore[return-value]
