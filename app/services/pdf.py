# FASE B: ekstraksi teks + analisis struktur PDF (Momen A — ATS Format Report).
# Deterministik, tidak pakai LLM: BLUEPRINT.md §10 LANGKAH 2 catatan teknis.

import fitz  # PyMuPDF

from app.schemas import FormatIssue, StructureReport

# Whitelist kasar font "aman" untuk ATS. Font di luar ini (atau custom-embedded
# subset) ditandai sebagai warning, bukan blocker keras.
_STANDARD_FONT_KEYWORDS = (
    "arial", "helvetica", "times", "calibri", "cambria", "georgia",
    "verdana", "courier", "garamond", "tahoma", "trebuchet", "segoe",
)

# Ambang batas heuristik header/footer — dikalibrasi kasar (ADJUSTMENT_PLAN.md §12).
_HEADER_FOOTER_MARGIN_RATIO = 0.08

# Multi-kolom asli (2 kolom berdampingan yang membuat ATS salah baca urutan)
# punya blok kiri & kanan yang TUMPANG TINDIH di rentang-y yang sama, dan itu
# terjadi di sebagian BESAR tinggi halaman — bukan cuma satu baris kontak di
# header atau satu baris daftar skill. Dikalibrasi dengan CV nyata (single-
# column tapi punya strip kontak & skill 2-kolom kecil) supaya tidak salah
# tandai — lihat ADJUSTMENT_PLAN.md §12.
_COLUMN_OVERLAP_MIN_POINTS = 5
_COLUMN_OVERLAP_PAGE_FRACTION = 0.25


class PDFUnreadableError(Exception):
    """CV tidak bisa dibuka/dibaca sebagai PDF -> dipetakan ke HTTP 422."""


def _has_real_multi_column(left: list, right: list, page_height: float) -> bool:
    """True hanya jika blok kiri & kanan tumpang tindih di rentang-y yang sama
    (bukan cuma ada blok di kedua sisi halaman) sepanjang porsi besar halaman."""
    if not left or not right:
        return False
    overlaps = []
    for lb in left:
        ly0, ly1 = lb[1], lb[3]
        for rb in right:
            ry0, ry1 = rb[1], rb[3]
            o0, o1 = max(ly0, ry0), min(ly1, ry1)
            if o1 - o0 > _COLUMN_OVERLAP_MIN_POINTS:
                overlaps.append((o0, o1))
    if not overlaps:
        return False
    overlaps.sort()
    merged = [overlaps[0]]
    for s, e in overlaps[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    total = sum(e - s for s, e in merged)
    return (total / page_height) > _COLUMN_OVERLAP_PAGE_FRACTION


def extract(data: bytes) -> tuple[str, StructureReport]:
    """Ekstrak raw_text + structure_report dari bytes PDF."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PDFUnreadableError(f"Gagal membuka file sebagai PDF: {e}")

    if doc.page_count == 0:
        raise PDFUnreadableError("PDF tidak memiliki halaman.")

    raw_text_parts: list[str] = []
    has_multi_column = False
    has_images = False
    has_tables = False
    has_nonstandard_font = False
    top_texts: dict[str, int] = {}
    bottom_texts: dict[str, int] = {}

    for page in doc:
        raw_text_parts.append(page.get_text())

        if page.get_images(full=True):
            has_images = True

        try:
            tables = page.find_tables()
            if tables and len(tables.tables) > 0:
                has_tables = True
        except Exception:
            pass  # deteksi tabel best-effort; jangan gagalkan seluruh parse

        page_width = page.rect.width
        page_height = page.rect.height
        blocks = page.get_text("blocks")
        text_blocks = [b for b in blocks if b[4].strip()]
        left = [b for b in text_blocks if (b[0] + b[2]) / 2 < page_width / 2]
        right = [b for b in text_blocks if (b[0] + b[2]) / 2 >= page_width / 2]
        if _has_real_multi_column(left, right, page_height):
            has_multi_column = True

        for f in page.get_fonts(full=True):
            font_name = f[3].split("+")[-1]  # buang prefix subset "ABCDEF+"
            if not any(kw in font_name.lower() for kw in _STANDARD_FONT_KEYWORDS):
                has_nonstandard_font = True

        for b in text_blocks:
            y0, y1, text = b[1], b[3], b[4].strip()
            if y1 < page_height * _HEADER_FOOTER_MARGIN_RATIO:
                top_texts[text] = top_texts.get(text, 0) + 1
            elif y0 > page_height * (1 - _HEADER_FOOTER_MARGIN_RATIO):
                bottom_texts[text] = bottom_texts.get(text, 0) + 1

    raw_text = "\n".join(raw_text_parts).strip()
    if not raw_text:
        raise PDFUnreadableError("Tidak ada teks yang bisa diekstrak dari PDF (kemungkinan hasil scan/gambar).")

    has_header_footer = doc.page_count > 1 and (
        any(v > 1 for v in top_texts.values()) or any(v > 1 for v in bottom_texts.values())
    )

    issues: list[FormatIssue] = []
    if has_multi_column:
        issues.append(FormatIssue(
            severity="fatal",
            type="multi_column",
            detail="CV memakai tata letak multi-kolom — ATS sering membaca urutan tersebut acak.",
        ))
    if has_images:
        issues.append(FormatIssue(
            severity="warning",
            type="photo",
            detail="Terdapat gambar/foto di CV — sebagian ATS gagal memprosesnya.",
        ))
    if has_tables:
        issues.append(FormatIssue(
            severity="warning",
            type="table",
            detail="CV memakai tabel — sebagian ATS membaca isi tabel dengan urutan yang salah.",
        ))
    if has_header_footer:
        issues.append(FormatIssue(
            severity="warning",
            type="header_footer",
            detail="Ada teks berulang di header/footer tiap halaman — sebagian ATS mencampurnya dengan isi utama.",
        ))
    if has_nonstandard_font:
        issues.append(FormatIssue(
            severity="warning",
            type="nonstandard_font",
            detail="Memakai font non-standar — berisiko gagal dirender atau salah dibaca oleh sebagian ATS.",
        ))

    return raw_text, StructureReport(issues=issues)
