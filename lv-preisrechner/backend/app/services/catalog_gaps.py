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

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.lv import LV, GapResolutionType, LVGapResolution
from app.models.pricing import TenantPriceOverride
from app.schemas.gaps import (
    CatalogGapEntry,
    GapSeverity,
    LVGapsReport,
    UniqueMissingMaterial,
)


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
    db: Session | None = None,
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

            # Material-JSONs tragen die DNA teils als "dna" (neueres
            # Schema), teils als "dna_pattern" (Legacy). Beide tolerieren.
            dna = str(m.get("dna") or m.get("dna_pattern") or "")
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

    # B+4.6: Resolutions laden (sofern Session uebergeben). Skip-Resolutions
    # filtern die entsprechenden material_dnas aus den offenen Gaps.
    resolutions_by_dna: dict[str, LVGapResolution] = {}
    skipped_dnas: set[str] = set()
    if db is not None:
        for r in (
            db.query(LVGapResolution)
            .filter(LVGapResolution.lv_id == lv.id)
            .all()
        ):
            resolutions_by_dna[r.material_dna] = r
            if r.resolution_type == GapResolutionType.SKIP.value:
                skipped_dnas.add(r.material_dna)

    if skipped_dnas:
        # Skipped Gaps aus Counter + Liste herausnehmen
        kept: list[CatalogGapEntry] = []
        missing = estimated = low_conf = 0
        for g in gaps:
            if g.material_dna in skipped_dnas:
                continue
            kept.append(g)
            if g.severity == GapSeverity.missing:
                missing += 1
            elif g.severity == GapSeverity.estimated:
                estimated += 1
            else:
                low_conf += 1
        gaps = kept

    # Sort: severity rank -> position_oz -> keep insertion order (stable)
    gaps.sort(key=lambda g: (GapSeverity.rank(g.severity), g.position_oz))

    gaps_count = len(gaps)
    # Defensiv: Counter-Invariante muss stimmen.
    assert gaps_count == missing + estimated + low_conf, (
        "gaps counter mismatch: "
        f"total={gaps_count} vs {missing}+{estimated}+{low_conf}"
    )

    # Unique-per-DNA Aggregation fuer das UI.
    uniq = _aggregate_unique_missing(gaps, resolutions_by_dna)

    return LVGapsReport(
        lv_id=str(lv.id),
        total_positions=len(positions),
        total_materials=total_mat,
        gaps_count=gaps_count,
        missing_count=missing,
        estimated_count=estimated,
        low_confidence_count=low_conf,
        gaps=gaps,
        unique_missing_materials=uniq,
    )


def _aggregate_unique_missing(
    gaps: list[CatalogGapEntry],
    resolutions_by_dna: dict[str, LVGapResolution],
) -> list[UniqueMissingMaterial]:
    """Dedupliziert Gaps per material_dna und aggregiert OZ-Liste + Menge.

    Enthaelt nur severity=missing. Estimated wird separat in den Counter
    aufgenommen, aber nicht als offenes Gap fuer User-Aktionen gelistet —
    die Position hat ja schon einen Schaetzpreis.
    """
    buckets: dict[str, UniqueMissingMaterial] = {}
    for g in gaps:
        if g.severity != GapSeverity.missing:
            continue
        bucket = buckets.get(g.material_dna)
        if bucket is None:
            resolution_info: dict[str, Any] | None = None
            r = resolutions_by_dna.get(g.material_dna)
            if r is not None:
                resolution_info = {
                    "resolution_type": r.resolution_type,
                    "resolved_value": r.resolved_value,
                    "created_at": r.created_at.isoformat(),
                }
            bucket = UniqueMissingMaterial(
                material_dna=g.material_dna,
                material_name=g.material_name,
                unit=g.unit,
                severity=g.severity,
                betroffene_positionen=[],
                total_required_amount=0.0,
                geschaetzter_preis=None,
                geschaetzter_preis_einheit=None,
                resolution=resolution_info,
            )
            buckets[g.material_dna] = bucket
        if g.position_oz and g.position_oz not in bucket.betroffene_positionen:
            bucket.betroffene_positionen.append(g.position_oz)
        bucket.total_required_amount += g.required_amount
    return list(buckets.values())


# --------------------------------------------------------------------------- #
# Resolve-Workflow (B+4.6)
# --------------------------------------------------------------------------- #
class GapResolutionError(ValueError):
    """Validierungsfehler beim Resolve einer Luecke."""


def _dna_to_override_fields(material_dna: str) -> tuple[str, str | None]:
    """Leitet (article_number-Platzhalter, manufacturer) aus dem DNA-Pattern.

    Das DNA-Pattern ist die einzige verlaessliche Identitaet fuer das
    Material — es gibt keine Artikelnummer, weil das Material ja per
    Definition nicht in der Preisliste ist. Der Override wird daher mit
    einer synthetischen article_number "DNA:<pattern>" angelegt. So kann
    der naechste Matcher-Lauf per DNA wieder zuordnen, wenn der
    price_lookup via name-Matching scheitert.
    """
    # Konvention: "DNA:"-Prefix signalisiert, dass es sich um eine
    # DNA-basierte Override-Zeile handelt (nicht echte Haendler-Artikelnr).
    synthetic_article = f"DNA:{material_dna}"
    # manufacturer aus erstem Segment
    parts = material_dna.split("|")
    manufacturer = parts[0].strip() if parts and parts[0].strip() else None
    return synthetic_article, manufacturer


def _material_name_for_override(material_dna: str) -> str:
    """Readable-Name aus DNA fuer den Override-Eintrag."""
    name = _material_name_from_dna(material_dna)
    return name or material_dna


def resolve_gap_manual_price(
    *,
    db: Session,
    lv: LV,
    tenant_id: str,
    user_id: str,
    material_dna: str,
    price_net: float,
    unit: str,
) -> LVGapResolution:
    """Erzeugt einen Tenant-Override + Audit-Eintrag, und kehrt letzteren zurueck.

    Der Override ist tenant-weit gueltig (nicht LV-spezifisch) — das ist
    das in Option A des Scope-Plans festgelegte Verhalten. Wenn der User
    spaeter einen anderen Preis will, ueberschreibt ein erneuter
    resolve_gap_manual_price-Call den bestehenden Override und
    Audit-Eintrag (Upsert ueber UniqueConstraint auf der Audit-Tabelle).
    """
    if not material_dna or not material_dna.strip():
        raise GapResolutionError("material_dna muss nicht-leerer String sein")
    if price_net is None or price_net <= 0:
        raise GapResolutionError("price_net muss > 0 sein")
    if not unit or not unit.strip():
        raise GapResolutionError("unit muss nicht-leerer String sein")
    unit = unit.strip()

    synthetic_article, manufacturer = _dna_to_override_fields(material_dna)
    mat_name = _material_name_for_override(material_dna)

    # Bestehender Override fuer dieselbe DNA? → updaten.
    existing_override = (
        db.query(TenantPriceOverride)
        .filter(
            TenantPriceOverride.tenant_id == tenant_id,
            TenantPriceOverride.article_number == synthetic_article,
        )
        .first()
    )
    now = datetime.now(UTC).date()
    if existing_override is not None:
        existing_override.override_price = float(price_net)
        existing_override.unit = unit
        existing_override.notes = f"Gap-Resolution (B+4.6): {mat_name}"
        override = existing_override
    else:
        override = TenantPriceOverride(
            tenant_id=tenant_id,
            article_number=synthetic_article,
            manufacturer=manufacturer,
            override_price=float(price_net),
            unit=unit,
            valid_from=now,
            valid_until=None,
            notes=f"Gap-Resolution (B+4.6): {mat_name}",
            created_by_user_id=user_id,
        )
        db.add(override)
    db.flush()  # override.id verfuegbar

    # Audit: bestehende Resolution dieses Typs wird ueberschrieben.
    existing_audit = (
        db.query(LVGapResolution)
        .filter(
            LVGapResolution.lv_id == lv.id,
            LVGapResolution.material_dna == material_dna,
            LVGapResolution.resolution_type == GapResolutionType.MANUAL_PRICE.value,
        )
        .first()
    )
    resolved_value = {"price_net": float(price_net), "unit": unit}
    if existing_audit is not None:
        existing_audit.resolved_value = resolved_value
        existing_audit.tenant_price_override_id = override.id
        existing_audit.created_by_user_id = user_id
        audit = existing_audit
    else:
        audit = LVGapResolution(
            lv_id=lv.id,
            tenant_id=tenant_id,
            material_dna=material_dna,
            resolution_type=GapResolutionType.MANUAL_PRICE.value,
            resolved_value=resolved_value,
            tenant_price_override_id=override.id,
            created_by_user_id=user_id,
        )
        db.add(audit)
    db.flush()
    return audit


def resolve_gap_skip(
    *,
    db: Session,
    lv: LV,
    tenant_id: str,
    user_id: str,
    material_dna: str,
) -> LVGapResolution:
    """Markiert einen Gap bewusst als akzeptiert (EP bleibt 0)."""
    existing = (
        db.query(LVGapResolution)
        .filter(
            LVGapResolution.lv_id == lv.id,
            LVGapResolution.material_dna == material_dna,
            LVGapResolution.resolution_type == GapResolutionType.SKIP.value,
        )
        .first()
    )
    if existing is not None:
        existing.created_by_user_id = user_id
        existing.resolved_value = {}
        db.flush()
        return existing
    audit = LVGapResolution(
        lv_id=lv.id,
        tenant_id=tenant_id,
        material_dna=material_dna,
        resolution_type=GapResolutionType.SKIP.value,
        resolved_value={},
        tenant_price_override_id=None,
        created_by_user_id=user_id,
    )
    db.add(audit)
    db.flush()
    return audit
