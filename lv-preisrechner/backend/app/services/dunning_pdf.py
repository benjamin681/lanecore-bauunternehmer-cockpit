"""Dunning-PDF (B+4.13).

Mahnung mit eskalierender Tonalitaet je Stufe:
  Stufe 1: Zahlungserinnerung — freundlich, Hinweis auf moegliches Versehen
  Stufe 2: Mahnung — ernst, Mahngebuehr + Verzugszinsen-Hinweis
  Stufe 3: Letzte Mahnung — Inkasso/Gerichts-Drohung
"""
from __future__ import annotations

from decimal import Decimal

import fitz
import structlog

from app.models.invoice import Dunning, Invoice
from app.models.lv import LV
from app.models.tenant import Tenant

log = structlog.get_logger(__name__)

PAGE_W, PAGE_H = fitz.paper_size("a4")
MX = 50.0
MY = 60.0


def _de_num(v: float, decimals: int = 2) -> str:
    s = f"{v:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _eur(v: float) -> str:
    return _de_num(v, 2) + " EUR"


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


_TITLES = {
    1: "ZAHLUNGSERINNERUNG",
    2: "MAHNUNG",
    3: "LETZTE MAHNUNG",
}

_BODY = {
    1: (
        "Sehr geehrte Damen und Herren,\n\n"
        "vermutlich ist es Ihrer Aufmerksamkeit entgangen, dass die unten "
        "aufgefuehrte Rechnung noch nicht beglichen ist. Bitte sehen Sie "
        "diese Erinnerung als freundlichen Hinweis — falls die Zahlung "
        "bereits unterwegs ist, betrachten Sie dieses Schreiben als "
        "gegenstandslos.\n\n"
        "Wir bitten um Ausgleich des offenen Betrags innerhalb der unten "
        "genannten Frist."
    ),
    2: (
        "Sehr geehrte Damen und Herren,\n\n"
        "trotz unserer Zahlungserinnerung haben wir keinen Zahlungseingang "
        "feststellen koennen. Wir mahnen Sie hiermit nachdruecklich, den "
        "offenen Betrag bis zur unten genannten Frist auszugleichen.\n\n"
        "Aufgrund des Verzuges sind wir gezwungen, eine Mahngebuehr und "
        "ggf. Verzugszinsen zu berechnen. Bitte verstehen Sie, dass wir "
        "bei weiterem Verzug rechtliche Schritte einleiten muessen."
    ),
    3: (
        "Sehr geehrte Damen und Herren,\n\n"
        "trotz wiederholter Mahnung ist der Rechnungsbetrag nicht "
        "ausgeglichen worden. Dies ist die letzte Mahnung vor Einleitung "
        "rechtlicher Massnahmen. Bei Ueberschreiten der unten genannten "
        "Frist behalten wir uns ausdruecklich vor, ein Inkasso-Unternehmen "
        "zu beauftragen oder gerichtliche Schritte einzuleiten.\n\n"
        "Saemtliche dadurch entstehenden Kosten gehen zu Ihren Lasten. "
        "Gerichtsstand ist der Sitz unseres Unternehmens."
    ),
}


def generate_dunning_pdf(
    dunning: Dunning, invoice: Invoice, lv: LV, tenant: Tenant
) -> bytes:
    """Erzeugt das Mahnungs-PDF passend zur Stufe."""
    level = int(dunning.dunning_level or 1)
    title = _TITLES.get(level, "MAHNUNG")
    body = _BODY.get(level, _BODY[1])

    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = MY

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

    # Empfaenger
    emp_y = MY + 70
    auftraggeber = (lv.auftraggeber or "").strip()
    if auftraggeber:
        page.insert_text((MX, emp_y), auftraggeber, fontsize=10, fontname="hebo")

    # Titel
    title_y = emp_y + 50
    page.insert_text((MX, title_y), title, fontsize=18, fontname="hebo")
    if level >= 2:
        # Roter / fetter Hinweis-Block
        page.draw_rect(
            (MX, title_y + 25, MX + 220, title_y + 45),
            color=(0.85, 0, 0) if level == 3 else (0.9, 0.55, 0.0),
            fill=(0.97, 0.94, 0.94) if level == 3 else (0.99, 0.96, 0.91),
        )
        page.insert_text(
            (MX + 6, title_y + 39),
            f"MAHNSTUFE {level}",
            fontsize=10,
            fontname="hebo",
            color=(0.85, 0, 0) if level == 3 else (0.9, 0.55, 0.0),
        )

    # Rechnungs-Info rechts
    info_y = title_y + 24
    info_left = PAGE_W - MX - 220
    page.insert_text(
        (info_left, info_y),
        f"Rechnungsnummer: {invoice.invoice_number}",
        fontsize=10,
        fontname="hebo",
    )
    if invoice.due_date:
        page.insert_text(
            (info_left, info_y + 14),
            f"urspr. faellig:  {invoice.due_date.strftime('%d.%m.%Y')}",
            fontsize=9,
        )
    page.insert_text(
        (info_left, info_y + 28),
        f"Mahnungsdatum:   {dunning.dunning_date.strftime('%d.%m.%Y')}",
        fontsize=9,
    )
    page.insert_text(
        (info_left, info_y + 42),
        f"Frist:           {dunning.due_date.strftime('%d.%m.%Y')}",
        fontsize=9,
        fontname="hebo",
    )

    # Body
    y = title_y + 80
    for paragraph in body.split("\n\n"):
        for line in _wrap(paragraph, 90):
            page.insert_text((MX, y), line, fontsize=10)
            y += 13
        y += 6

    # Forderungs-Tabelle
    y += 16
    page.draw_line((MX, y), (PAGE_W - MX, y))
    y += 14
    open_amount = float(
        Decimal(str(invoice.betrag_brutto)) - Decimal(str(invoice.paid_amount or 0))
    )
    page.insert_text((MX, y), "Offener Rechnungsbetrag", fontsize=10)
    page.insert_text((PAGE_W - MX - 100, y), _eur(open_amount), fontsize=10)
    y += 13
    if float(dunning.mahngebuehr_betrag or 0) > 0:
        page.insert_text((MX, y), f"Mahngebuehr Stufe {level}", fontsize=10)
        page.insert_text(
            (PAGE_W - MX - 100, y),
            _eur(float(dunning.mahngebuehr_betrag)),
            fontsize=10,
        )
        y += 13
    if float(dunning.mahnzinsen_betrag or 0) > 0:
        page.insert_text((MX, y), "Verzugszinsen", fontsize=10)
        page.insert_text(
            (PAGE_W - MX - 100, y),
            _eur(float(dunning.mahnzinsen_betrag)),
            fontsize=10,
        )
        y += 13
    page.draw_line((MX, y), (PAGE_W - MX, y))
    y += 14
    total = (
        open_amount
        + float(dunning.mahngebuehr_betrag or 0)
        + float(dunning.mahnzinsen_betrag or 0)
    )
    page.insert_text((MX, y), "Zu zahlender Gesamtbetrag", fontsize=12, fontname="hebo")
    page.insert_text(
        (PAGE_W - MX - 100, y), _eur(total), fontsize=12, fontname="hebo"
    )

    # Frist-Hinweis
    y += 28
    page.insert_text(
        (MX, y),
        f"Bitte ueberweisen Sie den Gesamtbetrag bis spaetestens "
        f"{dunning.due_date.strftime('%d.%m.%Y')} auf das unten genannte Konto.",
        fontsize=10,
    )

    # Bank
    y += 22
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

    out = doc.tobytes(deflate=True)
    doc.close()
    log.info(
        "dunning_pdf_generated",
        invoice_id=invoice.id,
        dunning_id=dunning.id,
        level=level,
        bytes=len(out),
    )
    return out
