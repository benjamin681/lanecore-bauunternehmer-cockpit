"""PDF-Filler: Original-LV öffnen, EP/GP einfügen → neues PDF speichern.

Strategie: Pragmatisch & robust — wir können Layout nicht exakt replizieren,
also generieren wir eine Anlage "LV mit Preisen" als strukturiertes Angebot
direkt auf separaten Seiten an das Original-PDF.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
import structlog

from app.core.config import settings
from app.models.lv import LV

log = structlog.get_logger()


def _euro(value: float) -> str:
    # Verwende EUR statt €-Zeichen, weil PyMuPDF-Standard-Fonts kein € rendern
    # (mappt sonst auf Mittelpunkt "·" als Fallback).
    return f"{value:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def _de_num(value: float, decimals: int = 2) -> str:
    """Deutsche Zahl: 1.895,00 statt 1.895.00 oder 1,895.00"""
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _wrap_text(text: str, max_chars_per_line: int = 40, max_lines: int = 2) -> list[str]:
    """Einfaches Wortumbruch-Helper fuer PDF-Tabellen-Zellen."""
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_chars_per_line:
            current = f"{current} {w}".strip()
        else:
            if current:
                lines.append(current)
            if len(lines) >= max_lines:
                # Letztes Wort + Ellipsis
                last = lines[-1]
                if len(last) + 3 <= max_chars_per_line:
                    lines[-1] = last + "..."
                return lines
            current = w
    if current:
        lines.append(current)
    return lines[:max_lines] if lines else [""]


def _oz_sort_key(oz: str) -> tuple:
    """Natural-Sort fuer OZ wie 610.1, 610.10, 620.621.5.

    Zerlegt in Integer-Tupel fuer korrekte numerische Sortierung.
    """
    if not oz:
        return (9999,)
    parts = []
    for part in str(oz).replace(" ", "").split("."):
        try:
            parts.append((0, int(part)))
        except ValueError:
            parts.append((1, part))  # Strings nach Zahlen einsortieren
    return tuple(parts)


def generate_filled_pdf_bytes(lv: LV, tenant_firma: str) -> bytes:
    """Erzeugt ausgefülltes PDF als Bytes (wird in DB persistiert)."""
    if not lv.original_pdf_bytes:
        raise ValueError("Kein Original-PDF in DB gespeichert")

    doc = fitz.open(stream=bytes(lv.original_pdf_bytes), filetype="pdf")
    try:
        _insert_deckblatt(doc, lv, tenant_firma)
        _append_kalkulation(doc, lv)
        import io

        buf = io.BytesIO()
        doc.save(buf, garbage=4, deflate=True)
        log.info("pdf_generated", lv_id=lv.id, size=buf.tell())
        return buf.getvalue()
    finally:
        doc.close()


def generate_filled_pdf(lv: LV, tenant_firma: str) -> Path:
    """Legacy: schreibt auf Disk. Bitte generate_filled_pdf_bytes nutzen."""
    from io import BytesIO

    data = generate_filled_pdf_bytes(lv, tenant_firma)
    out_dir = settings.upload_dir / "lvs" / lv.tenant_id / "ausgefuellt"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{lv.id}_ausgefuellt.pdf"
    out_path.write_bytes(data)
    return out_path


def _insert_deckblatt(doc: fitz.Document, lv: LV, tenant_firma: str) -> None:
    """Neues Deckblatt vorne einfügen."""
    page = doc.new_page(pno=0, width=595, height=842)  # A4
    y = 80.0
    page.insert_text(
        (60, y),
        f"ANGEBOT - {tenant_firma}",  # ASCII-Minus statt Em-Dash (Font rendert Em-Dash als .)
        fontsize=22,
        fontname="helv",
        color=(0.1, 0.1, 0.4),
    )
    y += 36
    if lv.projekt_name:
        page.insert_text((60, y), f"Projekt: {lv.projekt_name}", fontsize=14, fontname="helv")
        y += 20
    if lv.auftraggeber:
        page.insert_text(
            (60, y), f"Auftraggeber: {lv.auftraggeber}", fontsize=12, fontname="helv"
        )
        y += 20

    y += 30
    page.insert_text(
        (60, y),
        f"Angebotssumme netto: {_euro(lv.angebotssumme_netto)}",
        fontsize=16,
        fontname="helv",
        color=(0, 0.4, 0),
    )
    y += 40
    page.insert_text(
        (60, y),
        f"Positionen gesamt: {lv.positionen_gesamt}",
        fontsize=11,
        fontname="helv",
    )
    y += 16
    page.insert_text(
        (60, y),
        f"Davon sicher gematcht: {lv.positionen_gematcht}",
        fontsize=11,
        fontname="helv",
    )
    y += 16
    if lv.positionen_unsicher:
        page.insert_text(
            (60, y),
            f"Zur manuellen Pruefung: {lv.positionen_unsicher}",
            fontsize=11,
            fontname="helv",
            color=(0.7, 0.2, 0),
        )

    # Hinweis: Positionen ohne Preis in der Preisliste wurden nicht kalkuliert
    # (keine Schein-Preise aus Modellwissen - ehrlicher Fallback)
    manual_count = sum(1 for p in lv.positions if (p.konfidenz or 0) == 0.0 and (p.ep or 0) == 0.0)
    if manual_count > 0:
        y += 16
        page.insert_text(
            (60, y),
            f"Positionen ohne Preis in Ihrer Preisliste (manuell ergaenzen): {manual_count}",
            fontsize=10,
            fontname="helv",
            color=(0.9, 0.4, 0.0),
        )

    # MwSt-Aufschluesselung direkt unter Netto-Summe
    netto = lv.angebotssumme_netto or 0.0
    mwst = netto * 0.19
    brutto = netto + mwst
    y += 30
    page.insert_text(
        (60, y),
        f"zzgl. 19% MwSt: {_euro(mwst)}",
        fontsize=11,
        fontname="helv",
        color=(0.3, 0.3, 0.3),
    )
    y += 16
    page.insert_text(
        (60, y),
        f"Angebotssumme brutto: {_euro(brutto)}",
        fontsize=13,
        fontname="helv",
        color=(0, 0.4, 0),
    )

    page.insert_text(
        (60, 790),
        "Erstellt mit LaneCore AI - LV-Preisrechner",
        fontsize=8,
        fontname="helv",
        color=(0.5, 0.5, 0.5),
    )


def _append_kalkulation(doc: fitz.Document, lv: LV) -> None:
    """Anlage mit tabellarischer Kalkulation."""
    # Layout-Konstanten
    MARGIN_L = 40
    MARGIN_R = 40
    MARGIN_T = 60
    LINE_H = 14
    PAGE_W = 595
    PAGE_H = 842

    # Spaltenbreiten (gesamt = PAGE_W - MARGIN_L - MARGIN_R = 515)
    COL_OZ = 50
    COL_KURZTEXT = 220
    COL_MENGE = 50
    COL_EINHEIT = 30
    COL_EP = 75
    COL_GP = 90

    def _x_cols() -> list[float]:
        x = float(MARGIN_L)
        return [x, x + COL_OZ, x + COL_OZ + COL_KURZTEXT,
                x + COL_OZ + COL_KURZTEXT + COL_MENGE,
                x + COL_OZ + COL_KURZTEXT + COL_MENGE + COL_EINHEIT,
                x + COL_OZ + COL_KURZTEXT + COL_MENGE + COL_EINHEIT + COL_EP]

    def _new_page() -> fitz.Page:
        p = doc.new_page(width=PAGE_W, height=PAGE_H)
        p.insert_text(
            (MARGIN_L, 30),
            f"Kalkulation — {lv.projekt_name or 'LV'}",
            fontsize=12,
            fontname="hebo",
        )
        cols = _x_cols()
        y = 50
        p.insert_text((cols[0], y), "OZ", fontsize=9, fontname="hebo")
        p.insert_text((cols[1], y), "Kurztext", fontsize=9, fontname="hebo")
        p.insert_text((cols[2], y), "Menge", fontsize=9, fontname="hebo")
        p.insert_text((cols[3], y), "Einh.", fontsize=9, fontname="hebo")
        p.insert_text((cols[4] + 40, y), "EP", fontsize=9, fontname="hebo")
        p.insert_text((cols[5] + 55, y), "GP", fontsize=9, fontname="hebo")
        p.draw_line((MARGIN_L, y + 4), (PAGE_W - MARGIN_R, y + 4))
        return p

    page = _new_page()
    y = MARGIN_T + 10
    cols = _x_cols()

    # Positionen nach OZ natuerlich sortieren (610.1 vor 610.10)
    sorted_positions = sorted(lv.positions, key=lambda p: _oz_sort_key(p.oz or ""))

    for pos in sorted_positions:
        # Kurztext mit Textbox wrappen (bis 3 Zeilen)
        kurz_raw = (pos.kurztext or pos.titel or "").replace("\n", " ").strip()
        # Max. 160 Zeichen in 2 Zeilen Wrap
        kurz = kurz_raw[:160]
        kurz_lines = _wrap_text(kurz, max_chars_per_line=40, max_lines=2)
        extra_lines = max(0, len(kurz_lines) - 1)

        needed_h = LINE_H * (1 + extra_lines)
        if y + needed_h + 4 > PAGE_H - 50:
            page = _new_page()
            y = MARGIN_T + 10

        page.insert_text((cols[0], y), pos.oz or "", fontsize=8, fontname="helv")
        # Kurztext mehrzeilig
        for i, line in enumerate(kurz_lines):
            page.insert_text((cols[1], y + i * (LINE_H - 2)), line, fontsize=8, fontname="helv")

        page.insert_text(
            (cols[2], y), _de_num(pos.menge), fontsize=8, fontname="helv"
        )
        page.insert_text((cols[3], y), pos.einheit or "", fontsize=8, fontname="helv")

        # Wenn Position manuell zu pruefen ist (konfidenz=0, ep=0) -> klare Markierung
        needs_manual = (pos.konfidenz or 0) == 0.0 and (pos.ep or 0) == 0.0
        if needs_manual:
            page.insert_text(
                (cols[4] + 20, y),
                "manuell",
                fontsize=8,
                fontname="helv",
                color=(0.8, 0.3, 0.0),  # orange
            )
            page.insert_text(
                (cols[5] + 30, y),
                "--- EUR",
                fontsize=8,
                fontname="helv",
                color=(0.8, 0.3, 0.0),
            )
        else:
            page.insert_text(
                (cols[4] + 20, y),
                _euro(pos.ep),
                fontsize=8,
                fontname="helv",
            )
            page.insert_text(
                (cols[5] + 30, y),
                _euro(pos.gp),
                fontsize=8,
                fontname="helv",
                color=(0, 0, 0),
            )

        # WICHTIG: Interne Warnings (z.B. "Kein Preis: |Profile|UW75|") werden NICHT
        # mehr im PDF gezeigt — die sind fuer den Empfaenger verwirrend und wirken
        # unprofessionell. Sie bleiben in lv.warnungen fuer interne Pruefung im UI.
        y += max(LINE_H, needed_h)

    # Summenzeile
    if y + 30 > PAGE_H - 50:
        page = _new_page()
        y = MARGIN_T + 10
    y += 12
    page.draw_line((MARGIN_L, y), (PAGE_W - MARGIN_R, y))
    y += 14
    page.insert_text(
        (cols[4] - 30, y),
        "Angebotssumme netto:",
        fontsize=10,
        fontname="hebo",
    )
    page.insert_text(
        (cols[5] + 20, y),
        _euro(lv.angebotssumme_netto),
        fontsize=11,
        fontname="hebo",
        color=(0, 0.4, 0),
    )
