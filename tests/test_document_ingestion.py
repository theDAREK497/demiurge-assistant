from zipfile import ZIP_DEFLATED, ZipFile

from worldbuilder_core.services.document_ingestion import (
    _is_safe_near_duplicate,
    _read_docx,
    _simhash,
    _tail_overlap_at_boundary,
)


def test_document_overlap_never_starts_inside_a_word() -> None:
    text = "prefix alpha beta gamma delta"

    overlap = _tail_overlap_at_boundary(text, 14)

    assert overlap == "gamma delta"


def test_near_duplicate_guard_never_discards_a_changed_name() -> None:
    original = "Александр вошел в лабораторию и увидел красный кристалл. " * 70
    changed = original.replace("Александр", "Алексей", 1)

    distance = (_simhash(original.casefold()) ^ _simhash(changed.casefold())).bit_count()

    assert distance <= 3
    assert _is_safe_near_duplicate(original, changed) is False


def test_near_duplicate_guard_preserves_meaningful_punctuation() -> None:
    assert not _is_safe_near_duplicate(
        "Александр вошел в лабораторию.",
        "Александр вошел в лабораторию?",
    )


def test_near_duplicate_guard_accepts_typographic_variants() -> None:
    assert _is_safe_near_duplicate(
        '"Александр" - исследователь...',
        "“Александр” — исследователь…",
    )


def test_docx_tables_keep_rows_and_columns(tmp_path) -> None:
    document_path = tmp_path / "rolls.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Перед таблицей</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Бросок d6</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Результат</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>1-2</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Тихий след</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>3-6</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Опасная встреча</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p><w:r><w:t>После таблицы</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with ZipFile(document_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)

    paragraphs = list(_read_docx(document_path))

    assert paragraphs[0] == "Перед таблицей"
    assert paragraphs[2] == "После таблицы"
    assert paragraphs[1].startswith("[DOCUMENT TABLE]\n| Бросок d6 | Результат |")
    assert "| 1-2 | Тихий след |" in paragraphs[1]
    assert paragraphs[1].endswith("[/DOCUMENT TABLE]")
