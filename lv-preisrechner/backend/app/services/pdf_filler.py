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
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


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
        f"ANGEBOT — {tenant_firma}",
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
            f"Zur manuellen Prüfung: {lv.positionen_unsicher}",
            fontsize=11,
            fontname="helv",
            color=(0.7, 0.2, 0),
        )

    page.insert_text(
        (60, 790),
        "Erstellt mit LaneCore AI — LV-Preisrechner",
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

    for pos in lv.positions:
        # Kurztext ggf. kürzen
        kurz = (pos.kurztext or pos.titel or "").replace("\n", " ")[:90]

        if y + 2 * LINE_H > PAGE_H - 50:
            page = _new_page()
            y = MARGIN_T + 10

        page.insert_text((cols[0], y), pos.oz or "", fontsize=8, fontname="helv")
        page.insert_text((cols[1], y), kurz, fontsize=8, fontname="helv")
        page.insert_text(
            (cols[2], y), f"{pos.menge:,.2f}".replace(",", "."), fontsize=8, fontname="helv"
        )
        page.insert_text((cols[3], y), pos.einheit or "", fontsize=8, fontname="helv")
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

        if pos.warnung:
            y += LINE_H - 2
            page.insert_text(
                (cols[1], y),
                f"! {pos.warnung[:100]}",
                fontsize=7,
                fontname="heit",
                color=(0.7, 0.2, 0),
            )
        y += LINE_H

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
