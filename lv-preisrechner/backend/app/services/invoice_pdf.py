"""Invoice-PDF (B+4.13).

Erzeugt eine A4-Rechnung mit Briefkopf, Empfaenger, Positions-Tabelle,
Summen, Bankverbindung und Zahlungsfrist. Layout bewusst schlicht und
in einer Datei gehalten — re-use des bestehenden lv_pdf_export wuerde
private Helpers zu public machen.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import fitz
import structlog

from app.models.aufmass import Aufmass
from app.models.invoice import Invoice
from app.models.lv import LV
from app.models.offer import Offer, OfferPdfFormat
from app.models.tenant import Tenant

log = structlog.get_logger(__name__)


PAGE_W, PAGE_H = fitz.paper_size("a4")
MX = 50.0  # margin x
MY = 60.0  # margin y


def _de_num(value: float, decimals: int = 2) -> str:
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _eur(value: float) -> str:
    return _de_num(value, 2) + " EUR"


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + (1 if cur else 0) <= max_chars:
            cur.append(w)
            cur_len += len(w) + (1 if cur_len else 0)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def generate_invoice_pdf(
    invoice: Invoice,
    lv: LV,
    tenant: Tenant,
    *,
    db=None,
) -> bytes:
    """Generiert das Rechnungs-PDF.

    Position-Quelle:
      - Wenn invoice.source_aufmass_id gesetzt: Mengen aus Aufmaß
      - Sonst: Mengen aus LV-Positionen
    """
    positions = list(_resolve_positions(invoice, lv, db))

    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    y = MY
    # --- Briefkopf rechts oben ---
    firma = (tenant.company_name or tenant.name or "").strip()
    addr1 = (tenant.company_address_street or "").strip()
    addr2 = " ".join(
        s for s in [tenant.company_address_zip, tenant.company_address_city] if s
    ).strip()
    page.insert_text((MX, y), firma or "(Firmenname)", fontsize=11, fontname="hebo")
    if addr1:
        y += 13
        page.insert_text((MX, y), addr1, fontsize=9)
    if addr2:
        y += 11
        page.insert_text((MX, y), addr2, fontsize=9)
    if tenant.vat_id:
        y += 11
        page.insert_text((MX, y), f"USt-IdNr: {tenant.vat_id}", fontsize=8)

    # --- Empfaenger links unter Briefkopf ---
    emp_y = MY + 70
    auftraggeber = (lv.auftraggeber or "").strip()
    if auftraggeber:
        page.insert_text((MX, emp_y), auftraggeber, fontsize=10, fontname="hebo")

    # --- Titel + Header rechts ---
    title_y = emp_y + 50
    page.insert_text((MX, title_y), "RECHNUNG", fontsize=18, fontname="hebo")

    info_y = title_y + 22
    info_left = PAGE_W - MX - 200
    page.insert_text(
        (info_left, info_y),
        f"Rechnungsnummer: {invoice.invoice_number}",
        fontsize=10,
        fontname="hebo",
    )
    page.insert_text(
        (info_left, info_y + 14),
        f"Rechnungsdatum:  {invoice.invoice_date.strftime('%d.%m.%Y')}",
        fontsize=9,
    )
    if invoice.due_date:
        page.insert_text(
            (info_left, info_y + 28),
            f"Faellig bis:     {invoice.due_date.strftime('%d.%m.%Y')}",
            fontsize=9,
        )
    if lv.projekt_name:
        page.insert_text(
            (MX, info_y),
            f"Bauvorhaben:    {lv.projekt_name[:60]}",
            fontsize=9,
        )

    # --- Tabelle ---
    y = info_y + 60
    _draw_table_header(page, y)
    y += 16

    for pos in positions:
        if y > PAGE_H - MY - 120:
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            y = MY
            _draw_table_header(page, y)
            y += 16
        y = _draw_table_row(page, y, pos)

    # --- Summen ---
    y += 10
    page.draw_line((MX, y), (PAGE_W - MX, y))
    y += 14
    sum_left = PAGE_W - MX - 220
    val_left = PAGE_W - MX - 80
    page.insert_text((sum_left, y), "Netto", fontsize=10)
    page.insert_text((val_left, y), _eur(float(invoice.betrag_netto)), fontsize=10)
    y += 14
    page.insert_text((sum_left, y), "USt 19%", fontsize=10)
    page.insert_text((val_left, y), _eur(float(invoice.betrag_ust)), fontsize=10)
    y += 16
    page.insert_text((sum_left, y), "Gesamtbetrag", fontsize=12, fontname="hebo")
    page.insert_text(
        (val_left, y), _eur(float(invoice.betrag_brutto)), fontsize=12, fontname="hebo"
    )
    if float(invoice.paid_amount or 0) > 0:
        y += 14
        page.insert_text(
            (sum_left, y),
            f"davon bereits gezahlt: {_eur(float(invoice.paid_amount))}",
            fontsize=9,
        )
        offen = float(invoice.betrag_brutto) - float(invoice.paid_amount or 0)
        y += 12
        page.insert_text((sum_left, y), f"Offen: {_eur(offen)}", fontsize=10, fontname="hebo")

    # --- Zahlungsbedingungen ---
    y += 28
    if invoice.due_date:
        page.insert_text(
            (MX, y),
            f"Zahlbar ohne Abzug bis {invoice.due_date.strftime('%d.%m.%Y')}.",
            fontsize=9,
        )
    y += 14

    # --- Bankverbindung ---
    bank_lines = []
    if tenant.bank_name:
        bank_lines.append(f"Bank: {tenant.bank_name}")
    if tenant.bank_iban:
        bank_lines.append(f"IBAN: {tenant.bank_iban}")
    if tenant.bank_bic:
        bank_lines.append(f"BIC: {tenant.bank_bic}")
    if bank_lines:
        page.insert_text((MX, y), "Bankverbindung:", fontsize=9, fontname="hebo")
        y += 11
        for line in bank_lines:
            page.insert_text((MX, y), line, fontsize=9)
            y += 11

    # --- Footer ---
    y = PAGE_H - 50
    if tenant.signature_text:
        page.insert_text((MX, y), tenant.signature_text[:120], fontsize=8)

    out = doc.tobytes(deflate=True)
    doc.close()
    log.info(
        "invoice_pdf_generated",
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        bytes=len(out),
        positions=len(positions),
    )
    return out


def _draw_table_header(page: fitz.Page, y: float) -> None:
    page.insert_text((MX, y), "OZ", fontsize=8, fontname="hebo")
    page.insert_text((MX + 60, y), "Beschreibung", fontsize=8, fontname="hebo")
    page.insert_text((MX + 280, y), "Menge", fontsize=8, fontname="hebo")
    page.insert_text((MX + 330, y), "Einh.", fontsize=8, fontname="hebo")
    page.insert_text((MX + 380, y), "EP", fontsize=8, fontname="hebo")
    page.insert_text((MX + 450, y), "GP", fontsize=8, fontname="hebo")
    page.draw_line((MX, y + 4), (PAGE_W - MX, y + 4))


def _draw_table_row(page: fitz.Page, y: float, pos) -> float:
    page.insert_text((MX, y), (getattr(pos, "oz", "") or "")[:14], fontsize=8)
    desc = getattr(pos, "kurztext", "") or getattr(pos, "titel", "") or ""
    lines = _wrap(desc, 36)
    for i, line in enumerate(lines[:2]):
        page.insert_text((MX + 60, y + i * 10), line, fontsize=8)
    page.insert_text(
        (MX + 280, y),
        _de_num(float(getattr(pos, "menge", 0) or 0), 2),
        fontsize=8,
    )
    page.insert_text(
        (MX + 330, y), (getattr(pos, "einheit", "") or "")[:6], fontsize=8
    )
    page.insert_text(
        (MX + 380, y),
        _eur(float(getattr(pos, "ep", 0) or 0)),
        fontsize=8,
    )
    page.insert_text(
        (MX + 450, y),
        _eur(float(getattr(pos, "gp", 0) or 0)),
        fontsize=8,
    )
    rows_used = max(1, min(len(lines), 2))
    return y + 10 * rows_used + 4


def _resolve_positions(invoice: Invoice, lv: LV, db) -> list:
    """Liefert die fuer die Rechnung relevanten Positionen.

    Wenn die Rechnung aus einem Aufmaß stammt, werden die gemessenen
    Mengen + entsprechende GPs verwendet. Sonst die LV-Positionen.
    """
    from types import SimpleNamespace

    if invoice.source_aufmass_id and db is not None:
        a = db.get(Aufmass, invoice.source_aufmass_id)
        if a is not None:
            by_lv = {p.lv_position_id: p for p in a.positions}
            shadows = []
            for orig in lv.positions:
                au = by_lv.get(orig.id)
                if au is None:
                    shadows.append(orig)
                else:
                    shadows.append(
                        SimpleNamespace(
                            oz=orig.oz,
                            titel=orig.titel,
                            kurztext=orig.kurztext,
                            menge=float(au.gemessene_menge),
                            einheit=orig.einheit,
                            ep=float(au.ep),
                            gp=float(au.gp_aufmass),
                        )
                    )
            return shadows
    # Fallback: LV-Positionen
    return list(lv.positions)
