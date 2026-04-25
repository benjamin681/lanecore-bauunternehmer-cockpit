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
    """Erzeugt ausgefülltes PDF als Bytes (wird in DB persistiert).

    Strategie:
    1. Original-LV-Seiten direkt ausfuellen (EP, GP, Angebotenes Fabrikat)
    2. Neues Deckblatt vorne
    3. Kalkulations-Anlage hinten (als zweite Ansicht fuer den Kunden)
    """
    if not lv.original_pdf_bytes:
        raise ValueError("Kein Original-PDF in DB gespeichert")

    doc = fitz.open(stream=bytes(lv.original_pdf_bytes), filetype="pdf")
    try:
        # 1. Original-LV direkt befuellen (bevor Deckblatt davor kommt, damit
        #    Seitennummern in Search nicht verschoben sind)
        _fill_original_lv(doc, lv)
        # 2. Deckblatt vorne
        _insert_deckblatt(doc, lv, tenant_firma)
        # 3. Kalkulations-Anlage am Ende als Zusammenfassung
        _append_kalkulation(doc, lv)
        import io

        buf = io.BytesIO()
        doc.save(buf, garbage=4, deflate=True)
        log.info("pdf_generated", lv_id=lv.id, size=buf.tell())
        return buf.getvalue()
    finally:
        doc.close()


def _fill_original_lv(doc: fitz.Document, lv: LV) -> None:
    """Traegt EP, GP und Angebotenes Fabrikat direkt ins Original-LV.

    Heuristik (funktioniert fuer gaengige LV-Layouts von Habau, Gross, etc.):
    - EP/GP-Felder sind typisch leere Linien ".........................  ........................."
    - Angebotenes Fabrikat erscheint als "Angebotenes\nFabriakt: ..." (Tippfehler im LV!) oder "Angebotenes Fabrikat: ..."
    - OZ-Nummer steht typischerweise oberhalb in der Zeile davor

    Wir matchen Positionen ueber OZ-Nummern + Menge (zur Validierung).
    Nur Positionen mit gueltigem EP>0 werden eingetragen (manuelle bleiben leer).
    """
    # Map OZ -> Position fuer schnelles Lookup
    pos_by_oz = {}
    for p in lv.positions:
        if p.oz:
            pos_by_oz[p.oz.strip()] = p

    if not pos_by_oz:
        log.warning("fill_original_lv_no_positions", lv_id=lv.id)
        return

    filled_count = 0
    # Nur Original-Seiten verarbeiten (vor eventuellem Anhang)
    for page_idx in range(doc.page_count):
        page = doc.load_page(page_idx)
        try:
            filled_count += _fill_page(page, pos_by_oz)
        except Exception as e:
            log.warning("fill_page_failed", page=page_idx, err=str(e))

    log.info("original_lv_filled", lv_id=lv.id, positions=filled_count)


def _fill_page(page: fitz.Page, pos_by_oz: dict) -> int:
    """Fuellt EP/GP/Fabrikat fuer alle auf der Seite gefundenen OZs.

    Returns: Anzahl ausgefuellter Positionen auf dieser Seite.
    """
    # Text mit Koordinaten extrahieren (blocks/lines/spans)
    text_dict = page.get_text("dict")
    filled = 0

    # 1) Alle Text-Blocks sammeln mit Position
    lines_with_coords: list[tuple[str, fitz.Rect]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            line_text = ""
            line_bbox = None
            for span in line.get("spans", []):
                line_text += span.get("text", "")
                bbox = span.get("bbox")
                if bbox and line_bbox is None:
                    line_bbox = fitz.Rect(bbox)
                elif bbox and line_bbox is not None:
                    line_bbox |= fitz.Rect(bbox)
            if line_text.strip() and line_bbox:
                lines_with_coords.append((line_text, line_bbox))

    # 2) Finde OZ-Treffer + nachfolgende "..."-Muster fuer EP/GP
    # Typisches Muster:
    #    "610.18"
    #    "Fenster / Tuer..."
    #    "2,00 Stk"
    #    ".........................  ........................."  ← EP + GP Leerstellen
    import re

    # Dot-Patterns (leere EP/GP-Felder) vorab lokalisieren
    dot_lines = [(t, r) for (t, r) in lines_with_coords if re.fullmatch(r"\s*\.{10,}[\s\.]*", t)]

    for idx, (text, rect) in enumerate(lines_with_coords):
        # OZ-Muster: "610.18", "1.9.1.1.10", "01.01.005" etc.
        # B+4.10: re.match statt fullmatch — Salach-LV haelt OZ und
        # Kurztext in derselben Zeile (z.B. "59.10.0010. Innenwand,
        # d=100mm"), waehrend Habau/Gross-LVs die OZ in eigener Zeile
        # haben. Beide Faelle werden jetzt erfasst, durch Anker `^`
        # und Lookahead auf Whitespace/EOL nach der OZ-Sequenz.
        text_stripped = text.strip()
        oz_match = re.match(
            r"^(\d+(?:\.\d+){1,5})\.?(?=\s|$)", text_stripped
        )
        if not oz_match:
            continue
        oz_candidates = [oz_match.group(1), oz_match.group(1) + "."]
        pos = None
        for oz_try in oz_candidates:
            if oz_try in pos_by_oz:
                pos = pos_by_oz[oz_try]
                break
        if pos is None:
            continue

        # Nur ausfuellen wenn EP gueltig
        if not pos.ep or pos.ep <= 0:
            continue

        # Suche naechste EP+GP-Dotline (2 Dot-Gruppen mit Leerzeichen dazwischen).
        # Fabrikat-Felder haben nur EINE Dot-Gruppe, Summen-Felder oft auch.
        # Window bis naechste OZ oder 80 Zeilen (Stuttgart-LV hat lange Textbloecke).
        dot_rect = None
        search_end = min(len(lines_with_coords), idx + 80)
        # Stoppe bei naechster OZ, damit wir nicht in nachfolgende Position greifen
        for j in range(idx + 1, search_end):
            next_text, next_rect = lines_with_coords[j]
            if j > idx + 2 and re.match(
                r"^(\d+(?:\.\d+){1,5})\.?(?=\s|$)", next_text.strip()
            ):
                # naechste OZ -> abbrechen
                break
            # EP+GP-Muster: 2 Dot-Gruppen mit Whitespace dazwischen
            if re.search(r"\.{15,}\s+\.{15,}", next_text):
                dot_rect = next_rect
                break

        if dot_rect is None:
            continue

        # Dots aufteilen: EP-Feld links, GP-Feld rechts.
        # Wir teilen das Rechteck in zwei Haelften.
        mid_x = dot_rect.x0 + (dot_rect.width * 0.55)
        ep_right_x = mid_x - 5
        gp_right_x = dot_rect.x1 - 5

        # Werte einfuegen - rechtsbuendig gegenueber Spalten-Ende
        ep_txt = _euro_short(pos.ep)
        gp_txt = _euro_short(pos.gp)

        # Textbreite schaetzen (ca. 4.5pt pro Zeichen bei 9pt)
        def _twidth(s: str) -> float:
            return len(s) * 4.6

        ep_x = max(dot_rect.x0 + 5, ep_right_x - _twidth(ep_txt))
        gp_x = max(mid_x + 5, gp_right_x - _twidth(gp_txt))
        y_txt = dot_rect.y0 + dot_rect.height * 0.75

        try:
            page.insert_text((ep_x, y_txt), ep_txt, fontsize=9, fontname="helv", color=(0, 0, 0.4))
            page.insert_text((gp_x, y_txt), gp_txt, fontsize=9, fontname="helv", color=(0, 0, 0.4))
            filled += 1
        except Exception:
            continue

        # 3) Angebotenes Fabrikat: suche in naechsten 15 Zeilen nach "Angebotenes"
        if pos.angebotenes_fabrikat:
            for fabr_idx in range(idx + 1, min(idx + 30, len(lines_with_coords))):
                fabr_text, fabr_rect = lines_with_coords[fabr_idx]
                if "ngebotenes" in fabr_text:
                    # Naechste Zeile enthaelt "Fabriakt: ....." oder "Fabrikat: ....."
                    if fabr_idx + 1 < len(lines_with_coords):
                        label_text, label_rect = lines_with_coords[fabr_idx + 1]
                        if re.search(r"[Ff]abri?ka?t", label_text):
                            # Finde dots in selber Zeile
                            dot_match = re.search(r"\.{10,}", label_text)
                            if dot_match:
                                # Schaetzung: Text direkt vor dem Punkt-Bereich
                                label_prefix_len = dot_match.start()
                                # Zeichenbreite schaetzen
                                char_w = label_rect.width / max(len(label_text), 1)
                                text_x = label_rect.x0 + (label_prefix_len * char_w)
                                y_fabr = label_rect.y0 + label_rect.height * 0.75
                                try:
                                    page.insert_text(
                                        (text_x, y_fabr),
                                        pos.angebotenes_fabrikat[:70],
                                        fontsize=8,
                                        fontname="helv",
                                        color=(0, 0, 0.4),
                                    )
                                except Exception:
                                    pass
                    break

    return filled


def _euro_short(value: float) -> str:
    """Zahl fuer EP/GP-Feld: '1.234,56' (ohne EUR - steht schon im Header)."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
