"""PDF-Angebot Generator — Professionelles Kundenangebot als PDF.

Erstellt ein 2-seitiges PDF:
  Seite 1: Kundenangebot (Anschreiben mit LV-Positionen)
  Seite 2: Bestellliste (intern, für den Unternehmer)

Verwendet reportlab für die PDF-Generierung.
"""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Formatierung ────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4  # 210 x 297 mm

# Colors
LANECORE_BLUE = colors.HexColor("#1e40af")
LANECORE_LIGHT = colors.HexColor("#eff6ff")
HEADER_BG = colors.HexColor("#1e3a5f")
ROW_ALT = colors.HexColor("#f8fafc")
BORDER_COLOR = colors.HexColor("#cbd5e1")
INTERN_RED = colors.HexColor("#dc2626")


def _eur(value: float | None) -> str:
    """Formatiert einen Betrag als deutschen EUR-String: 1.234,56 EUR."""
    if value is None:
        return "–"
    # German formatting: dot as thousands separator, comma as decimal
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} EUR"


def _num(value: float | None, decimals: int = 1) -> str:
    """Formatiert eine Zahl deutsch: 1.234,5."""
    if value is None:
        return "–"
    fmt = f"{{:,.{decimals}f}}"
    return fmt.format(value).replace(",", "X").replace(".", ",").replace("X", ".")


def _generate_angebotsnummer() -> str:
    """Generiert eine Angebotsnummer: AN-YYYY-NNNN."""
    today = date.today()
    # Simple sequential based on day-of-year for uniqueness
    import random
    seq = random.randint(1000, 9999)
    return f"AN-{today.year}-{seq:04d}"


# ── PDF-Generierung ─────────────────────────────────────────────────────────


def generate_angebot_pdf(kalkulation: dict, filename: str = "") -> bytes:
    """Generiert ein professionelles Angebot-PDF aus den Kalkulationsdaten.

    Args:
        kalkulation: Vollständige Kalkulation (von erstelle_kalkulation).
        filename: Ursprünglicher Dateiname des Bauplans.

    Returns:
        PDF als bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    style_title = ParagraphStyle(
        "AngebotTitle",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=LANECORE_BLUE,
        spaceAfter=6 * mm,
        spaceBefore=0,
    )
    style_subtitle = ParagraphStyle(
        "AngebotSubtitle",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=3 * mm,
    )
    style_normal = ParagraphStyle(
        "AngebotNormal",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
    )
    style_small = ParagraphStyle(
        "AngebotSmall",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    )
    style_header_right = ParagraphStyle(
        "HeaderRight",
        parent=styles["Normal"],
        fontSize=9,
        alignment=2,  # RIGHT
        textColor=colors.HexColor("#475569"),
    )
    style_intern_title = ParagraphStyle(
        "InternTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=INTERN_RED,
        spaceAfter=3 * mm,
    )
    style_intern_warning = ParagraphStyle(
        "InternWarning",
        parent=styles["Normal"],
        fontSize=10,
        textColor=INTERN_RED,
        spaceBefore=2 * mm,
        spaceAfter=4 * mm,
    )

    elements: list = []
    kundenangebot = kalkulation.get("kundenangebot", {})
    positionen = kalkulation.get("positionen", [])
    bestellliste = kalkulation.get("bestellliste", [])

    today_str = date.today().strftime("%d.%m.%Y")
    angebots_nr = _generate_angebotsnummer()
    projekt_name = filename.replace(".pdf", "").replace("_", " ") if filename else "Trockenbau-Projekt"
    plantyp = kalkulation.get("plantyp", "")
    geschoss = kalkulation.get("geschoss", "")

    # ══════════════════════════════════════════════════════════════════════════
    # SEITE 1: Kundenangebot
    # ══════════════════════════════════════════════════════════════════════════

    # ── Header ──
    header_data = [
        [
            Paragraph("<b>LaneCore AI</b><br/>Bauunternehmer-Cockpit", ParagraphStyle(
                "LogoStyle", parent=styles["Normal"], fontSize=14,
                textColor=LANECORE_BLUE, leading=18,
            )),
            Paragraph(
                f"Datum: {today_str}<br/>Angebot-Nr: {angebots_nr}",
                style_header_right,
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[100 * mm, 70 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, LANECORE_BLUE),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # ── Titel ──
    elements.append(Paragraph("ANGEBOT", style_title))

    # ── Projektinfo ──
    info_lines = [f"<b>Projekt:</b> {projekt_name}"]
    if plantyp:
        info_lines.append(f"<b>Plantyp:</b> {plantyp}")
    if geschoss:
        info_lines.append(f"<b>Geschoss:</b> {geschoss}")
    info_lines.append(f"<b>Angebotsnummer:</b> {angebots_nr}")
    info_lines.append(f"<b>Datum:</b> {today_str}")

    for line in info_lines:
        elements.append(Paragraph(line, style_normal))
    elements.append(Spacer(1, 6 * mm))

    # ── Flächen-Übersicht ──
    deckenfl = kundenangebot.get("deckenflaeche_m2", 0)
    wandfl = kundenangebot.get("wandflaeche_m2", 0)
    if deckenfl or wandfl:
        elements.append(Paragraph(
            f"<b>Deckenfläche:</b> {_num(deckenfl)} m² &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"<b>Wandfläche:</b> {_num(wandfl)} m²",
            style_normal,
        ))
        elements.append(Spacer(1, 4 * mm))

    # ── Positionen-Tabelle (LV-Stil) ──
    elements.append(Paragraph("<b>Leistungsverzeichnis — Positionen</b>", style_subtitle))

    col_widths = [12 * mm, 62 * mm, 18 * mm, 14 * mm, 28 * mm, 30 * mm]
    table_header = ["Pos.", "Bezeichnung", "Menge", "Einh.", "EP (netto)", "GP (netto)"]

    table_data = [table_header]
    for idx, pos in enumerate(positionen, 1):
        ep = pos.get("einzelpreis")
        gp = pos.get("gesamtpreis")
        table_data.append([
            f"{idx:02d}",
            Paragraph(pos.get("bezeichnung", ""), style_normal),
            _num(pos.get("menge"), 1),
            pos.get("einheit", ""),
            _eur(ep) if ep is not None else "n/v",
            _eur(gp) if gp is not None else "n/v",
        ])

    pos_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table_style_cmds = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        # Alignment
        ("ALIGN", (0, 0), (0, -1), "CENTER"),  # Pos
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),   # Menge
        ("ALIGN", (3, 0), (3, -1), "CENTER"),  # Einheit
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),  # Preise
        # Borders
        ("LINEBELOW", (0, 0), (-1, 0), 1, LANECORE_BLUE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BORDER_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # Alternating row colors
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
        # Light bottom border per row
        table_style_cmds.append(("LINEBELOW", (0, i), (-1, i), 0.25, BORDER_COLOR))

    pos_table.setStyle(TableStyle(table_style_cmds))
    elements.append(pos_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Zusammenfassung / Kalkulation ──
    elements.append(Paragraph("<b>Zusammenfassung</b>", style_subtitle))

    summary_col_widths = [110 * mm, 54 * mm]

    summary_rows = [
        ["Material (netto Einkauf)", _eur(kundenangebot.get("material_einkauf"))],
        [
            f"Material-Aufschlag ({_num(kundenangebot.get('material_aufschlag_prozent', 0), 0)}%)",
            _eur(kundenangebot.get("material_aufschlag_eur")),
        ],
        ["Material gesamt", _eur(kundenangebot.get("material_verkauf"))],
    ]

    # Montagekosten
    stunden = kundenangebot.get("lohnstunden", 0)
    satz = kundenangebot.get("stundensatz", 0)
    summary_rows.append([
        f"Montagekosten ({_num(stunden, 1)} Std. x {_eur(satz).replace(' EUR', '')} EUR/Std.)",
        _eur(kundenangebot.get("lohnkosten")),
    ])

    # Zusatzkosten
    zusatzkosten = kundenangebot.get("zusatzkosten", [])
    for zk in zusatzkosten:
        summary_rows.append([
            zk.get("bezeichnung", "Zusatzkosten"),
            _eur(zk.get("betrag")),
        ])

    if kundenangebot.get("zusatzkosten_summe", 0) > 0 and len(zusatzkosten) > 1:
        summary_rows.append([
            "Zusatzkosten gesamt",
            _eur(kundenangebot.get("zusatzkosten_summe")),
        ])

    # Netto / MwSt / Brutto
    summary_rows.append(["", ""])  # spacer row
    summary_rows.append(["NETTO-SUMME", _eur(kundenangebot.get("angebot_netto"))])
    summary_rows.append([
        f"MwSt. {kundenangebot.get('mwst_prozent', 19)}%",
        _eur(kundenangebot.get("mwst_eur")),
    ])
    summary_rows.append(["BRUTTOSUMME", _eur(kundenangebot.get("angebot_brutto"))])

    summary_table = Table(summary_rows, colWidths=summary_col_widths)
    num_rows = len(summary_rows)
    summary_style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, BORDER_COLOR),
    ]

    # Bold Netto line
    netto_idx = num_rows - 3
    summary_style_cmds.extend([
        ("FONTNAME", (0, netto_idx), (-1, netto_idx), "Helvetica-Bold"),
        ("LINEABOVE", (0, netto_idx), (-1, netto_idx), 1, colors.black),
    ])

    # Bold + large Brutto line
    brutto_idx = num_rows - 1
    summary_style_cmds.extend([
        ("FONTNAME", (0, brutto_idx), (-1, brutto_idx), "Helvetica-Bold"),
        ("FONTSIZE", (0, brutto_idx), (-1, brutto_idx), 12),
        ("TEXTCOLOR", (0, brutto_idx), (-1, brutto_idx), LANECORE_BLUE),
        ("LINEABOVE", (0, brutto_idx), (-1, brutto_idx), 1.5, LANECORE_BLUE),
        ("TOPPADDING", (0, brutto_idx), (-1, brutto_idx), 6),
        ("BOTTOMPADDING", (0, brutto_idx), (-1, brutto_idx), 6),
        ("BACKGROUND", (0, brutto_idx), (-1, brutto_idx), LANECORE_LIGHT),
    ])

    summary_table.setStyle(TableStyle(summary_style_cmds))
    elements.append(summary_table)
    elements.append(Spacer(1, 8 * mm))

    # ── Footer: Zahlungsbedingungen ──
    elements.append(Paragraph("<b>Zahlungsbedingungen</b>", style_normal))
    elements.append(Spacer(1, 1 * mm))
    elements.append(Paragraph(
        "Zahlbar innerhalb von 14 Tagen nach Rechnungsstellung ohne Abzug. "
        "Dieses Angebot ist 30 Tage gültig.",
        style_small,
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "Alle Preise verstehen sich zzgl. der gesetzlichen Mehrwertsteuer, sofern nicht anders angegeben. "
        "Änderungen und Irrtümer vorbehalten. Es gelten unsere allgemeinen Geschäftsbedingungen.",
        style_small,
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(
        f"<i>Erstellt mit LaneCore AI — {today_str}</i>",
        ParagraphStyle("Footer", parent=style_small, textColor=colors.HexColor("#94a3b8")),
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # SEITENUMBRUCH → SEITE 2: Bestellliste (intern)
    # ══════════════════════════════════════════════════════════════════════════
    from reportlab.platypus import PageBreak
    elements.append(PageBreak())

    # Intern-Header
    elements.append(Paragraph("BESTELLLISTE", style_intern_title))
    elements.append(Paragraph(
        "INTERN — Nicht an Kunden weitergeben!",
        style_intern_warning,
    ))
    elements.append(Paragraph(
        f"Projekt: {projekt_name} &nbsp;|&nbsp; Datum: {today_str} &nbsp;|&nbsp; Angebot: {angebots_nr}",
        style_normal,
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── Bestellliste: nach Lieferant gruppiert ──
    for lieferant in bestellliste:
        anbieter = lieferant.get("anbieter", "Unbekannt")
        items = lieferant.get("positionen", [])
        summe = lieferant.get("summe_netto", 0)

        elements.append(Paragraph(
            f'<b>{anbieter}</b> &nbsp;({len(items)} Positionen, Summe: {_eur(summe)})',
            ParagraphStyle(
                "LieferantHeader", parent=style_normal,
                fontSize=10, spaceBefore=4 * mm, spaceAfter=2 * mm,
                textColor=HEADER_BG,
            ),
        ))

        best_col_widths = [70 * mm, 14 * mm, 18 * mm, 14 * mm, 24 * mm, 24 * mm]
        best_header = ["Material", "Kat.", "Menge", "Einh.", "EP (netto)", "GP (netto)"]
        best_data = [best_header]
        for item in items:
            best_data.append([
                Paragraph(item.get("bezeichnung", ""), style_small),
                item.get("kategorie", "")[:6],
                _num(item.get("menge"), 1),
                item.get("einheit", ""),
                _eur(item.get("einzelpreis")) if item.get("einzelpreis") is not None else "–",
                _eur(item.get("gesamtpreis")) if item.get("gesamtpreis") is not None else "–",
            ])

        best_table = Table(best_data, colWidths=best_col_widths, repeatRows=1)
        best_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef2f2")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, INTERN_RED),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i in range(1, len(best_data)):
            best_style.append(("LINEBELOW", (0, i), (-1, i), 0.25, BORDER_COLOR))
            if i % 2 == 0:
                best_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fff5f5")))

        best_table.setStyle(TableStyle(best_style))
        elements.append(best_table)
        elements.append(Spacer(1, 2 * mm))

    # Gesamt-Einkaufssumme
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(
        f'<b>Gesamt-Einkauf (netto): {_eur(kundenangebot.get("material_einkauf"))}</b>',
        ParagraphStyle(
            "GesamtEinkauf", parent=style_normal,
            fontSize=11, textColor=INTERN_RED,
        ),
    ))
    elements.append(Paragraph(
        f'Verkaufspreis Material (inkl. {_num(kundenangebot.get("material_aufschlag_prozent", 0), 0)}% Aufschlag): '
        f'{_eur(kundenangebot.get("material_verkauf"))}',
        style_normal,
    ))
    elements.append(Paragraph(
        f'Marge Material: {_eur(kundenangebot.get("material_aufschlag_eur"))}',
        style_normal,
    ))

    # Build PDF
    doc.build(elements)
    return buffer.getvalue()
