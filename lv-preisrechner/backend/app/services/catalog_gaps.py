"""Katalog-Luecken-Auswertung pro LV (B+4.3.0c).

Liest ausschliesslich aus den bereits persistierten Materialien-JSONs
pro Position (``Position.materialien``). Keine neuen Lookups, keine
Matcher-Aufrufe, keine DB-Schreibvorgaenge.

Definitionen siehe ``docs/b430c_baseline.md``. Klassifikations-Regel:

- price_source == "not_found"                           -> missing
- price_source == "estimated"                           -> estimated
- price_source == "supplier_price" und conf < 0.5       -> low_confidence
  (nur wenn include_low_confidence=True)

Alle anderen Materialien (override, legacy, sauberes supplier_price,
oder Zeilen ohne price_source) werden ignoriert.
"""

from __future__ import annotations

from typing import Any

from app.models.lv import LV
from app.schemas.gaps import CatalogGapEntry, GapSeverity, LVGapsReport


_LOW_CONFIDENCE_THRESHOLD = 0.5


def _material_name_from_dna(dna: str) -> str:
    """Leitet einen menschenlesbaren Namen aus dem DNA-Pattern ab.

    Format: ``Hersteller|Kategorie|Produktname|Abmessungen|Variante``.
    Fuer den Namen werden Produktname (Teil 3) und Abmessungen
    (Teil 4) verwendet. Leere Segmente werden weggelassen.

    Fallback-Kette: Produktname+Abmessungen -> Variante allein ->
    irgendein nicht-leerer Teil -> ``dna`` selbst. Niemals leerer
    String.
    """
    if not dna:
        return ""
    if "|" not in dna:
        return dna
    parts = dna.split("|")
    # 0=Hersteller 1=Kategorie 2=Produktname 3=Abmessungen 4=Variante
    chosen = [p.strip() for p in parts[2:4] if p and p.strip()]
    if chosen:
        return " ".join(chosen)
    # Fallback: Variante oder irgendein nicht-leerer Teil
    for p in parts[::-1]:
        if p and p.strip():
            return p.strip()
    return dna


def _classify(m: dict[str, Any], include_low_confidence: bool) -> GapSeverity | None:
    src = m.get("price_source")
    conf = m.get("match_confidence")
    if src == "not_found":
        return GapSeverity.missing
    if src == "estimated":
        return GapSeverity.estimated
    if (
        include_low_confidence
        and src == "supplier_price"
        and conf is not None
        and conf < _LOW_CONFIDENCE_THRESHOLD
    ):
        return GapSeverity.low_confidence
    return None


def compute_lv_gaps(
    lv: LV,
    include_low_confidence: bool = False,
) -> LVGapsReport:
    """Erzeugt einen Katalog-Luecken-Report fuer das uebergebene LV.

    Iteriert ueber alle Positionen (stabile Reihenfolge nach
    ``position.reihenfolge``) und deren ``materialien``-JSON-Liste.
    Klassifiziert pro Material die severity, sammelt nur die Gaps,
    befuellt die Summary-Counter und sortiert deterministisch.

    Counter-Invariante: ``gaps_count == missing + estimated +
    low_confidence``. Wird per Assertion zur Runtime geprueft.
    """
    gaps: list[CatalogGapEntry] = []
    missing = estimated = low_conf = 0
    total_mat = 0

    positions = sorted(lv.positions or [], key=lambda p: p.reihenfolge)
    for pos in positions:
        for m in pos.materialien or []:
            total_mat += 1
            sev = _classify(m, include_low_confidence)
            if sev is None:
                continue
            if sev == GapSeverity.missing:
                missing += 1
            elif sev == GapSeverity.estimated:
                estimated += 1
            else:
                low_conf += 1

            src = m.get("price_source") or ""
            conf_raw = m.get("match_confidence")
            # missing-Gaps tragen keine Confidence (None). Bei anderen
            # Severities wird der Wert wie im JSON uebernommen.
            if sev == GapSeverity.missing:
                confidence: float | None = None
            else:
                confidence = float(conf_raw) if conf_raw is not None else None

            dna = str(m.get("dna") or "")
            position_name = pos.erkanntes_system or (pos.kurztext or "")[:60]
            gaps.append(
                CatalogGapEntry(
                    position_id=str(pos.id),
                    position_oz=str(pos.oz or ""),
                    position_name=position_name,
                    material_name=_material_name_from_dna(dna),
                    material_dna=dna,
                    required_amount=float(m.get("menge") or 0.0),
                    unit=str(m.get("einheit") or ""),
                    severity=sev,
                    price_source=str(src),
                    match_confidence=confidence,
                    source_description=str(m.get("source_description") or ""),
                    needs_review=bool(m.get("needs_review", False)),
                )
            )

    # Sort: severity rank -> position_oz -> keep insertion order (stable)
    gaps.sort(key=lambda g: (GapSeverity.rank(g.severity), g.position_oz))

    gaps_count = len(gaps)
    # Defensiv: Counter-Invariante muss stimmen.
    assert gaps_count == missing + estimated + low_conf, (
        "gaps counter mismatch: "
        f"total={gaps_count} vs {missing}+{estimated}+{low_conf}"
    )

    return LVGapsReport(
        lv_id=str(lv.id),
        total_positions=len(positions),
        total_materials=total_mat,
        gaps_count=gaps_count,
        missing_count=missing,
        estimated_count=estimated,
        low_confidence_count=low_conf,
        gaps=gaps,
    )
