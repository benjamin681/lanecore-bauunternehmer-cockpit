"""B+4.10 — Original-LV-PDF mit Preis-Overlay.

Use-Case
--------
Der Auftraggeber schickt seinem Trockenbauer ein LV-PDF mit leeren EP-
und GP-Spalten. Der Trockenbauer kalkuliert in Kalkulane die Preise
und muss das **Original-PDF** mit eingetragenen Preisen zurueck
schicken — nicht ein neu generiertes Angebot mit eigenem Layout.

Standard-Praxis im Bauwesen: Auftraggeber vergleicht direkt seine
eigene LV-Tabelle Bieter-fuer-Bieter, OZ fuer OZ, in identischem
Layout. Der Endpoint dieses Service liefert genau das.

Abgrenzung zum verwandten Service ``lv_pdf_export.py``
------------------------------------------------------
``lv_pdf_export.py`` (B+4.8) erzeugt ein **eigenstaendiges**
Angebots-PDF im Kalkulane-Layout: Briefkopf, Empfaenger,
Positionstabelle, Hauptgruppen-Subtotals, Summen-Block, Footer mit
AGB. Use-Case: Verkaufs-Dokument fuers Archiv des Trockenbauers
oder als Nachweis bei Verhandlungen.

``lv_original_filled.py`` (dieser Service, B+4.10) verzichtet auf
jede Layout-Aenderung. Er **mutiert das Original-PDF nicht** sondern
oeffnet es, schreibt EP/GP via PyMuPDF-Overlay direkt auf die
existierenden leeren Felder und liefert die Bytes zurueck. Use-Case:
Direkt-Rueckschicken an den Auftraggeber.

Beide Endpoints sind komplementaer und beide nuetzlich. Die
Abgrenzung muss im UI klar sein (siehe Frontend-Buttons).

Implementation
--------------
Wiederverwendung von ``pdf_filler._fill_original_lv``: dieselbe
OZ-Matching- + Dot-Pattern-Logik wie der bestehende Composite-Export
fuer "ausgefuellt" — nur ohne das Deckblatt einzufuegen und ohne die
Kalkulations-Anlage anzuhaengen.
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF
import structlog

from app.models.lv import LV
from app.services.pdf_filler import _fill_original_lv

log = structlog.get_logger()


class LVOriginalFilledError(RuntimeError):
    """Fehler beim Erzeugen des befuellten Original-PDFs."""


def generate_original_filled_pdf(lv: LV) -> bytes:
    """Erzeugt eine PDF-Kopie des Original-LVs mit eingetragenen Preisen.

    Args:
        lv: Hydratiertes LV-Objekt mit ``original_pdf_bytes`` und
            geladenen ``positions`` (mindestens ``oz``, ``ep``, ``gp``,
            optional ``angebotenes_fabrikat``).

    Returns:
        PDF als bytes. Anzahl Seiten und Layout sind identisch zum
        Original — nur in den existierenden Punkt-Linien-Spalten
        wurden EP und GP textuell ueberlagert.

    Raises:
        LVOriginalFilledError: Wenn kein Original-PDF in der DB
            persistiert ist oder kein einziges OZ-Match auf den
            Original-Seiten gefunden wurde (Layout-Inkompatibilitaet).
    """
    if not lv.original_pdf_bytes:
        raise LVOriginalFilledError(
            "Kein Original-PDF in der DB gespeichert — "
            "bitte das LV neu hochladen."
        )

    doc = fitz.open(stream=bytes(lv.original_pdf_bytes), filetype="pdf")
    try:
        # _fill_original_lv schreibt direkt auf die Original-Seiten und
        # logt selbst die Anzahl der gefuellten Positionen.
        _fill_original_lv(doc, lv)
        # Bewusst KEIN _insert_deckblatt und KEIN _append_kalkulation —
        # der Caller will das nackte Original-Layout zurueck.

        buf = io.BytesIO()
        doc.save(buf, garbage=4, deflate=True)
        log.info(
            "lv_original_filled_done",
            lv_id=lv.id,
            pages=doc.page_count,
            size=buf.tell(),
        )
        return buf.getvalue()
    finally:
        doc.close()
