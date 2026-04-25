"""B+4.8 — Angebots-PDF-Export.

Generiert ein eigenstaendiges Angebots-PDF (kein Re-Annotation des
Original-LVs, das macht ``pdf_filler.py``). Layout:

    Seite 1+ (A4 portrait, 595×842pt):
      - Briefkopf-Block oben links: Tenant-Firmenname + Anschrift
      - Empfaenger-Block oben rechts: Auftraggeber + Bauvorhaben
      - Angebots-Header: Angebotsnummer, Datum, LV-Bezeichnung
      - Positionstabelle mit OZ, Kurztext (gewrappt), Menge, Einheit, EP, GP
      - Zwischensummen pro Hauptgruppe (OZ-Praefix vor zweitem Punkt)
      - Gesamtsumme netto / 19% MwSt / brutto
      - Footer mit Bankverbindung + AGB/Zahlungsbedingungen

Implementation via PyMuPDF (`fitz`) — schon im Stack, keine neuen
Dependencies. Wir nutzen denselben Helper-Stil wie
``pdf_filler.py`` (deutsche Zahlen, EUR-Postfix statt €-Glyph weil
Standard-Fonts kein € rendern).
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

import fitz  # PyMuPDF
import structlog

from app.models.lv import LV
from app.models.tenant import Tenant

log = structlog.get_logger()


# --------------------------------------------------------------------------- #
# Format-Helpers (lokale Kopien, damit lv_pdf_export ohne pdf_filler-Import
# verwendbar bleibt — die Helper sind kompakt genug).
# --------------------------------------------------------------------------- #
def _de_num(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _euro(value: float) -> str:
    return f"{_de_num(value, 2)} EUR"


def _wrap(text: str, max_chars: int) -> list[str]:
    """Word-wrap, schneidet bei einzelnen ueberlangen Tokens hart."""
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(w) > max_chars:
            # Hartes Token splitten
            while w:
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(w[:max_chars])
                w = w[max_chars:]
            continue
        if len(cur) + len(w) + 1 <= max_chars:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _hauptgruppe(oz: str) -> str:
    """Aus OZ '59.10.0010' den Gruppen-Praefix '59.10' bilden."""
    if not oz:
        return ""
    parts = oz.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return parts[0] if parts else ""


# --------------------------------------------------------------------------- #
# Layout-Konstanten
# --------------------------------------------------------------------------- #
PAGE_W = 595.0
PAGE_H = 842.0
MARGIN_X = 40.0
MARGIN_Y = 60.0
COL_OZ = MARGIN_X
COL_TEXT = COL_OZ + 65
COL_MENGE = COL_TEXT + 270
COL_EH = COL_MENGE + 50
COL_EP = COL_EH + 30
COL_GP = COL_EP + 70
TEXT_WRAP_CHARS = 50
ROW_GAP_PT = 14
HEADER_FONT_SIZE = 9
TITLE_FONT_SIZE = 18
DEFAULT_FOOTER = (
    "Es gelten unsere Allgemeinen Geschaeftsbedingungen. "
    "Zahlungsbedingungen: 14 Tage netto ab Rechnungsdatum, "
    "ohne Abzug. Skonto und Boni nur nach gesonderter Vereinbarung."
)


# --------------------------------------------------------------------------- #
# Kerntyp + oeffentliche API
# --------------------------------------------------------------------------- #
class LVExportError(RuntimeError):
    """Fehler bei der Angebots-PDF-Erzeugung."""


def generate_angebot_pdf(lv: LV, tenant: Tenant) -> bytes:
    """Erzeugt das vollstaendige Angebots-PDF und liefert die Bytes.

    Wirft ``LVExportError`` bei Inkonsistenzen (z.B. LV ohne
    Positionen). Layout ist deterministisch — gleiche Eingaben =
    gleiche Bytes (modulo Erstellungs-Datum im Header).
    """
    if not lv.positions:
        raise LVExportError("LV hat keine Positionen — Export macht keinen Sinn.")

    cs = dict(tenant.company_settings or {})
    firma = (cs.get("firma") or tenant.name or "").strip()
    angebotsnr = _build_angebotsnummer(lv)
    erstell_datum = date.today()

    doc = fitz.open()
    page = _new_page(doc)
    y = MARGIN_Y

    # Briefkopf links + Empfaenger rechts
    y = _draw_briefkopf(page, y=y, firma=firma, settings=cs)
    _draw_empfaenger(page, y=MARGIN_Y, lv=lv)

    y = max(y, MARGIN_Y + 90) + 30

    # Titel-Block
    y = _draw_angebot_header(page, y=y, lv=lv, angebotsnr=angebotsnr,
                             erstell_datum=erstell_datum)

    # Tabelle
    sorted_positions = sorted(
        lv.positions, key=lambda p: (p.reihenfolge, p.oz or "")
    )
    y = _draw_table(doc, page, y, sorted_positions)

    # Summen
    y = _draw_summen(doc, page, y, lv)

    # Footer-Block (auf jeder Seite unten gleicher Inhalt)
    _draw_footer_all_pages(doc, settings=cs)

    out = BytesIO()
    doc.save(out)
    doc.close()
    log.info(
        "lv_pdf_export_done",
        lv_id=lv.id,
        positions=len(lv.positions),
        bytes=out.tell(),
    )
    return out.getvalue()


# --------------------------------------------------------------------------- #
# Drawing-Sub-Routines
# --------------------------------------------------------------------------- #
def _new_page(doc: fitz.Document) -> fitz.Page:
    return doc.new_page(width=PAGE_W, height=PAGE_H)


def _build_angebotsnummer(lv: LV) -> str:
    """Stabile Angebotsnummer aus LV-Erstelldatum + ID-Praefix."""
    created = lv.created_at if lv.created_at else datetime.now()
    return f"A{created.strftime('%Y%m%d')}-{lv.id[:6].upper()}"


def _draw_briefkopf(
    page: fitz.Page,
    *,
    y: float,
    firma: str,
    settings: dict,
) -> float:
    page.insert_text((MARGIN_X, y), firma or "(Firmenname)",
                     fontsize=12, fontname="hebo")
    y += 16
    for key in ("anschrift_zeile1", "anschrift_zeile2"):
        v = (settings.get(key) or "").strip()
        if v:
            page.insert_text((MARGIN_X, y), v, fontsize=9, fontname="helv")
            y += 12
    contact = " · ".join(
        s for s in [
            (settings.get("telefon") or "").strip(),
            (settings.get("email") or "").strip(),
        ] if s
    )
    if contact:
        page.insert_text((MARGIN_X, y), contact, fontsize=8,
                         fontname="helv", color=(0.4, 0.4, 0.4))
        y += 12
    return y


def _draw_empfaenger(page: fitz.Page, *, y: float, lv: LV) -> None:
    """Empfaenger-Block in der oberen rechten Spalte."""
    x = PAGE_W / 2 + 20
    page.insert_text((x, y), "Empfaenger:", fontsize=8,
                     fontname="helv", color=(0.4, 0.4, 0.4))
    y += 13
    name = (lv.auftraggeber or "Auftraggeber").strip()
    page.insert_text((x, y), name, fontsize=11, fontname="hebo")
    y += 15
    if lv.projekt_name:
        for line in _wrap(lv.projekt_name, 38):
            page.insert_text((x, y), line, fontsize=9, fontname="helv")
            y += 12


def _draw_angebot_header(
    page: fitz.Page,
    *,
    y: float,
    lv: LV,
    angebotsnr: str,
    erstell_datum: date,
) -> float:
    page.insert_text((MARGIN_X, y), "ANGEBOT",
                     fontsize=TITLE_FONT_SIZE, fontname="hebo",
                     color=(0.10, 0.20, 0.40))
    y += 22
    info_y = y
    page.insert_text((MARGIN_X, info_y), f"Angebotsnummer:  {angebotsnr}",
                     fontsize=9, fontname="helv")
    page.insert_text((MARGIN_X, info_y + 12),
                     f"Datum:                {erstell_datum.strftime('%d.%m.%Y')}",
                     fontsize=9, fontname="helv")
    if lv.projekt_name:
        page.insert_text((MARGIN_X, info_y + 24),
                         f"Bauvorhaben:        {lv.projekt_name[:60]}",
                         fontsize=9, fontname="helv")
    return info_y + 50


def _draw_table_header(page: fitz.Page, y: float) -> float:
    # Hintergrundbalken
    rect = fitz.Rect(MARGIN_X - 4, y - 11, PAGE_W - MARGIN_X + 4, y + 4)
    page.draw_rect(rect, color=(0.85, 0.88, 0.95), fill=(0.93, 0.95, 0.99))
    page.insert_text((COL_OZ, y), "OZ", fontsize=HEADER_FONT_SIZE, fontname="hebo")
    page.insert_text((COL_TEXT, y), "Bezeichnung", fontsize=HEADER_FONT_SIZE, fontname="hebo")
    page.insert_text((COL_MENGE, y), "Menge", fontsize=HEADER_FONT_SIZE, fontname="hebo")
    page.insert_text((COL_EH, y), "EH", fontsize=HEADER_FONT_SIZE, fontname="hebo")
    page.insert_text((COL_EP, y), "EP", fontsize=HEADER_FONT_SIZE, fontname="hebo")
    page.insert_text((COL_GP, y), "GP", fontsize=HEADER_FONT_SIZE, fontname="hebo")
    return y + 16


def _draw_table(
    doc: fitz.Document,
    page: fitz.Page,
    y: float,
    positions: list,
) -> float:
    y = _draw_table_header(page, y)
    current_group = None
    group_subtotal = 0.0

    for pos in positions:
        gruppe = _hauptgruppe(pos.oz or "")
        if gruppe and gruppe != current_group:
            # Zwischensumme der vorherigen Gruppe einziehen, falls vorhanden
            if current_group is not None and group_subtotal > 0:
                if y > PAGE_H - MARGIN_Y - 50:
                    page = _new_page(doc)
                    y = _draw_table_header(page, MARGIN_Y)
                y = _draw_subtotal(page, y, current_group, group_subtotal)
            current_group = gruppe
            group_subtotal = 0.0
            # Gruppen-Header
            if y > PAGE_H - MARGIN_Y - 40:
                page = _new_page(doc)
                y = _draw_table_header(page, MARGIN_Y)
            page.insert_text((MARGIN_X, y), f"Hauptgruppe {gruppe}",
                             fontsize=10, fontname="hebo",
                             color=(0.10, 0.20, 0.40))
            y += 16

        kurztext_lines = _wrap(pos.kurztext or "", TEXT_WRAP_CHARS)
        row_height = max(ROW_GAP_PT, len(kurztext_lines) * 11 + 4)

        if y + row_height > PAGE_H - MARGIN_Y - 40:
            page = _new_page(doc)
            y = _draw_table_header(page, MARGIN_Y)

        # OZ
        page.insert_text((COL_OZ, y), pos.oz or "", fontsize=9, fontname="helv")
        # Kurztext (mehrzeilig)
        for i, line in enumerate(kurztext_lines):
            page.insert_text((COL_TEXT, y + i * 11), line,
                             fontsize=9, fontname="helv")
        # Menge / EH rechts-buendig im Spaltenrahmen
        menge_str = _de_num(float(pos.menge or 0), 2)
        page.insert_text((COL_MENGE, y), menge_str,
                         fontsize=9, fontname="helv")
        page.insert_text((COL_EH, y), (pos.einheit or "")[:6],
                         fontsize=9, fontname="helv")
        ep = float(pos.ep or 0)
        gp = float(getattr(pos, "gp", None) or pos.menge * ep)
        page.insert_text((COL_EP, y), _euro(ep),
                         fontsize=9, fontname="helv")
        page.insert_text((COL_GP, y), _euro(gp),
                         fontsize=9, fontname="helv")
        group_subtotal += gp
        y += row_height

    # Letzte Gruppen-Subtotal nicht vergessen
    if current_group is not None and group_subtotal > 0:
        if y > PAGE_H - MARGIN_Y - 50:
            page = _new_page(doc)
            y = MARGIN_Y
        y = _draw_subtotal(page, y, current_group, group_subtotal)

    return y


def _draw_subtotal(page: fitz.Page, y: float, gruppe: str, subtotal: float) -> float:
    page.draw_line(
        fitz.Point(MARGIN_X, y),
        fitz.Point(PAGE_W - MARGIN_X, y),
        color=(0.7, 0.7, 0.75),
        width=0.4,
    )
    y += 12
    label = f"Zwischensumme {gruppe}"
    page.insert_text((COL_TEXT, y), label,
                     fontsize=9, fontname="hebo", color=(0.2, 0.2, 0.2))
    page.insert_text((COL_GP, y), _euro(subtotal),
                     fontsize=9, fontname="hebo", color=(0.2, 0.2, 0.2))
    return y + 18


def _draw_summen(
    doc: fitz.Document,
    page: fitz.Page,
    y: float,
    lv: LV,
) -> float:
    netto = float(lv.angebotssumme_netto or 0)
    mwst = round(netto * 0.19, 2)
    brutto = round(netto + mwst, 2)

    if y > PAGE_H - MARGIN_Y - 80:
        page = _new_page(doc)
        y = MARGIN_Y

    y += 14
    page.draw_line(
        fitz.Point(MARGIN_X, y),
        fitz.Point(PAGE_W - MARGIN_X, y),
        color=(0.10, 0.20, 0.40),
        width=1.0,
    )
    y += 16

    rows = [
        ("Gesamtsumme netto", netto, False),
        ("zzgl. 19 % USt.", mwst, False),
        ("Gesamtsumme brutto", brutto, True),
    ]
    for label, value, bold in rows:
        font = "hebo" if bold else "helv"
        size = 11 if bold else 10
        color = (0.10, 0.20, 0.40) if bold else (0.0, 0.0, 0.0)
        page.insert_text((COL_TEXT, y), label, fontsize=size,
                         fontname=font, color=color)
        page.insert_text((COL_GP, y), _euro(value), fontsize=size,
                         fontname=font, color=color)
        y += 18
    return y


def _draw_footer_all_pages(doc: fitz.Document, *, settings: dict) -> None:
    """Schreibt den Footer auf jede bestehende Seite."""
    bank_iban = (settings.get("iban") or "").strip()
    bank_bic = (settings.get("bic") or "").strip()
    bank_name = (settings.get("bank_name") or "").strip()
    ust_id = (settings.get("ust_id") or "").strip()
    text = (settings.get("footer_text") or DEFAULT_FOOTER).strip()

    bank_line = " · ".join(
        [s for s in [bank_name, bank_iban, bank_bic] if s]
    )
    legal_line = ust_id and f"USt-IdNr.: {ust_id}" or ""

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        y = PAGE_H - MARGIN_Y + 14
        # Trennlinie
        page.draw_line(
            fitz.Point(MARGIN_X, y),
            fitz.Point(PAGE_W - MARGIN_X, y),
            color=(0.7, 0.7, 0.75),
            width=0.4,
        )
        y += 10
        # Footer-Text gewrappt
        for line in _wrap(text, 110):
            page.insert_text((MARGIN_X, y), line, fontsize=7,
                             fontname="helv", color=(0.4, 0.4, 0.4))
            y += 9
        if bank_line:
            page.insert_text((MARGIN_X, y), bank_line, fontsize=7,
                             fontname="helv", color=(0.4, 0.4, 0.4))
            y += 9
        if legal_line:
            page.insert_text((MARGIN_X, y), legal_line, fontsize=7,
                             fontname="helv", color=(0.4, 0.4, 0.4))
            y += 9
        # Seitenzahl rechts
        page_label = f"Seite {page_idx + 1} von {doc.page_count}"
        page.insert_text(
            (PAGE_W - MARGIN_X - 60, PAGE_H - MARGIN_Y + 24),
            page_label, fontsize=7, fontname="helv", color=(0.4, 0.4, 0.4),
        )
