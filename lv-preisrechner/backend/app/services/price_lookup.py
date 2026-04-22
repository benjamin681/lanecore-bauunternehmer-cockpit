"""Preis-Lookup-Service mit 5-stufiger Fallback-Logik.

Dieser Service findet für einen Material-Bedarf (aus einem LV-Rezept) den
besten verfügbaren Preis eines Tenants. Er ist bewusst isoliert von der
Kalkulations-Pipeline — die Integration erfolgt in einem späteren Sub-Block.

Reihenfolge (erste Stufe mit Treffer gewinnt):

    1. TenantPriceOverride        — manuelle, verbindliche Überschreibung
    2. SupplierPriceEntry (neu)   — aktive Lieferanten-Preisliste, ggf. mit Rabatt
    3. PriceEntry (Legacy)        — bestehende Preislisten-Infrastruktur
    4. Heuristik                  — Ø über Kategorie+Einheit der letzten 12 Monate
    5. not_found                  — Trigger für manuelle UI-Eingabe

Designentscheidungen:
- Overrides werden NICHT mit Rabatt verrechnet (Override = finaler Wert).
- Der Audit-Trail (`lookup_details`) enthält je Stufe ein Dict mit dem
  jeweils geprüften Ergebnis — nützlich für UI-Tooltip und Debugging.
- Fuzzy-Matching via `material_normalizer.score_query_against_candidate`
  (asymmetrische Token-Coverage nach rapidfuzz-gestuetzter Normalisierung)
  mit Score ≥ 0.85 (entspricht 85 % Token-Coverage).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Literal

import structlog
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
    TenantDiscountRule,
    TenantPriceOverride,
)

log = structlog.get_logger()

FUZZY_MATCH_THRESHOLD = 0.85

# B+4.2.6 Option C Phase 2: Produkt-Code-Blacklist fuer Stage-2c-Pre-Filter.
# Kandidaten, deren `attributes.product_code_type` in dieser Liste steht UND
# deren `product_code_dimension` mit einer numerischen Dimension aus der
# Query uebereinstimmt, werden aus dem Match-Pool ausgeschlossen, bevor der
# Fuzzy-Scorer ueber sie entscheidet.
#
# Design: minimal, nur konkrete Regressions-Faelle mit Test-Case werden
# aufgenommen. Siehe docs/b426_optionC_phase2_baseline.md.
#
# {"UT"} deckt die PE-Folien-Regression (UT40 gewinnt gegen 40mm-Daemmung)
# aus dem E2E-Lauf vom 21.04.2026.
PRODUCT_CODE_BLACKLIST: frozenset[str] = frozenset({"UT"})


def should_exclude_by_blacklist(
    candidate_attrs: dict | None,
    query_material_name: str | None,
) -> bool:
    """Pure Pre-Filter-Funktion fuer Stage 2c (B+4.2.6 Option C Phase 2).

    Gibt True zurueck, wenn der Kandidat aus dem Match-Pool ausgeschlossen
    werden soll, weil

      1. sein `attributes.product_code_type` in
         :data:`PRODUCT_CODE_BLACKLIST` steht **und**
      2. seine `attributes.product_code_dimension` (numerisch) mit einer
         numerischen Dimension im `query_material_name` uebereinstimmt.

    Ohne beide Bedingungen zusammen: keine Filterung (return False).
    Das stellt sicher, dass echte Produkt-Varianten (DA125, WLG040,
    TC-Codes usw.) **nicht** gefiltert werden.

    """
    if not candidate_attrs:
        return False
    candidate_type = candidate_attrs.get("product_code_type")
    if not candidate_type or candidate_type not in PRODUCT_CODE_BLACKLIST:
        return False
    candidate_dim_raw = candidate_attrs.get("product_code_dimension")
    if candidate_dim_raw is None:
        return False
    # Dimension normieren: "40" / "040" / 40 → int 40.
    try:
        candidate_dim_int = int(str(candidate_dim_raw).lstrip("0") or "0")
    except (TypeError, ValueError):
        return False
    if candidate_dim_int == 0:
        return False
    if not query_material_name:
        return False
    # Alle Zahlen-Tokens aus der Query als int extrahieren.
    query_numbers = set()
    for raw in re.findall(r"\d+", query_material_name):
        try:
            query_numbers.add(int(raw.lstrip("0") or "0"))
        except ValueError:  # pragma: no cover
            continue
    return candidate_dim_int in query_numbers


PriceSource = Literal[
    "override",
    "supplier_price",
    "legacy_price",
    "estimated",
    "not_found",
]


# ---------------------------------------------------------------------------
# Ergebnis-Struktur
# ---------------------------------------------------------------------------
@dataclass
class PriceLookupResult:
    """Ergebnis eines Preis-Lookups inkl. Audit-Trail.

    Attribute:
        price:                    Finaler Preis (nach evt. Rabatt). None bei not_found.
        currency:                 ISO-Währung, default "EUR".
        unit:                     Einheit des finalen Preises (z. B. "m²", "kg").
        price_source:             Welche Stufe den Treffer geliefert hat.
        source_description:       Mensch-lesbare Kurzbegründung für UI-Tooltips.
        original_price:           Preis VOR Rabatt (nur bei supplier_price gesetzt).
        applied_discount_percent: Angewendeter Rabatt in Prozent (oder None).
        supplier_name:            Lieferant des Treffers (oder None).
        pricelist_id:             ID der Quell-Preisliste (oder None).
        entry_id:                 ID des konkreten Entries (oder None).
        match_confidence:         0.0 … 1.0, Qualität des Matches.
        needs_review:             True wenn Schätzung/not_found oder niedrige Konfidenz.
        lookup_details:           Geordnete Liste geprüfter Stufen (Audit-Trail).
    """

    price: Decimal | None
    currency: str
    unit: str
    price_source: PriceSource
    source_description: str
    original_price: Decimal | None = None
    applied_discount_percent: Decimal | None = None
    supplier_name: str | None = None
    pricelist_id: str | None = None
    entry_id: str | None = None
    match_confidence: float = 0.0
    needs_review: bool = False
    lookup_details: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------
def lookup_price(
    *,
    db: Session,
    tenant_id: str,
    material_name: str,
    unit: str,
    manufacturer: str | None = None,
    article_number: str | None = None,
    category: str | None = None,
    today: date | None = None,
) -> PriceLookupResult:
    """Führt den 5-stufigen Lookup aus.

    Args:
        db:             SQLAlchemy-Session (read-only genügt).
        tenant_id:      Tenant-UUID als String.
        material_name:  Produktbezeichnung (z. B. "CW-Profil 100x50x0,6").
        unit:           Gewünschte Einheit (z. B. "m²", "Stk.", "kg").
        manufacturer:   Optionaler Hersteller-Filter.
        article_number: Optionale Artikelnummer (höchste Match-Präzision).
        category:       Optionale Kategorie (hilft bei Rabatt und Schätzung).
        today:          Stichdatum für Gültigkeits-Prüfungen (Test-Injection).

    Returns:
        PriceLookupResult — immer eine Antwort; `price_source="not_found"`
        wenn keine Stufe getroffen hat.
    """
    ref_date = today or date.today()
    details: list[dict] = []

    # Stufe 1 — Override
    result = _try_override(
        db=db,
        tenant_id=tenant_id,
        material_name=material_name,
        unit=unit,
        manufacturer=manufacturer,
        article_number=article_number,
        today=ref_date,
        details=details,
    )
    if result is not None:
        result.lookup_details = details
        return result

    # Stufe 2 — aktive Lieferanten-Preisliste
    result = _try_supplier_price(
        db=db,
        tenant_id=tenant_id,
        material_name=material_name,
        unit=unit,
        manufacturer=manufacturer,
        article_number=article_number,
        category=category,
        today=ref_date,
        details=details,
    )
    if result is not None:
        result.lookup_details = details
        return result

    # Stufe 3 — Legacy-PriceEntry
    result = _try_legacy_price(
        db=db,
        tenant_id=tenant_id,
        material_name=material_name,
        unit=unit,
        manufacturer=manufacturer,
        category=category,
        details=details,
    )
    if result is not None:
        result.lookup_details = details
        return result

    # Stufe 4 — Heuristische Schätzung
    result = _try_estimate(
        db=db,
        tenant_id=tenant_id,
        unit=unit,
        category=category,
        today=ref_date,
        details=details,
    )
    if result is not None:
        result.lookup_details = details
        return result

    # Stufe 5 — nichts gefunden
    details.append({"stage": "not_found", "matched": False})
    return PriceLookupResult(
        price=None,
        currency="EUR",
        unit=unit,
        price_source="not_found",
        source_description="Kein Preis gefunden. Bitte manuell eingeben.",
        match_confidence=0.0,
        needs_review=True,
        lookup_details=details,
    )


# ---------------------------------------------------------------------------
# Interne Stufen
# ---------------------------------------------------------------------------
def _try_override(
    *,
    db: Session,
    tenant_id: str,
    material_name: str,
    unit: str,
    manufacturer: str | None,
    article_number: str | None,
    today: date,
    details: list[dict],
) -> PriceLookupResult | None:
    """Stufe 1 — Tenant-Override. Override gewinnt immer, keine Rabattierung."""
    q = db.query(TenantPriceOverride).filter(
        TenantPriceOverride.tenant_id == tenant_id,
        TenantPriceOverride.valid_from <= today,
        or_(
            TenantPriceOverride.valid_until.is_(None),
            TenantPriceOverride.valid_until >= today,
        ),
    )

    match: TenantPriceOverride | None = None
    how = ""
    if article_number:
        match = q.filter(TenantPriceOverride.article_number == article_number).first()
        if match:
            how = f"Artikelnummer {article_number}"
    if match is None and manufacturer:
        # Fallback ohne Artikelnummer: Hersteller + Einheit
        candidates = q.filter(
            TenantPriceOverride.manufacturer == manufacturer,
            TenantPriceOverride.unit == unit,
        ).all()
        match = _pick_best_name_match(candidates, material_name, lambda o: o.article_number)
        if match:
            how = f"Hersteller {manufacturer} + Einheit {unit}"

    details.append(
        {
            "stage": "override",
            "matched": match is not None,
            "match_criterion": how,
        }
    )
    if match is None:
        return None

    price = Decimal(str(match.override_price))
    return PriceLookupResult(
        price=price,
        currency="EUR",
        unit=match.unit,
        price_source="override",
        source_description=f"Tenant-Override ({how})",
        original_price=price,
        applied_discount_percent=None,
        supplier_name=None,
        pricelist_id=None,
        entry_id=match.id,
        match_confidence=1.0,
        needs_review=False,
    )


def _try_supplier_price(
    *,
    db: Session,
    tenant_id: str,
    material_name: str,
    unit: str,
    manufacturer: str | None,
    article_number: str | None,
    category: str | None,
    today: date,
    details: list[dict],
) -> PriceLookupResult | None:
    """Stufe 2 — aktive SupplierPriceList. Rabatt-Regel wird ggf. angewandt."""
    active_lists = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.tenant_id == tenant_id,
            SupplierPriceList.is_active.is_(True),
            SupplierPriceList.status != PricelistStatus.ARCHIVED.value,
        )
        .all()
    )
    if not active_lists:
        details.append({"stage": "supplier_price", "matched": False, "reason": "keine aktive Liste"})
        return None

    pricelist_ids = [pl.id for pl in active_lists]
    base_q = db.query(SupplierPriceEntry).filter(
        SupplierPriceEntry.tenant_id == tenant_id,
        SupplierPriceEntry.pricelist_id.in_(pricelist_ids),
    )

    match: SupplierPriceEntry | None = None
    how = ""
    confidence = 0.0

    # a) Artikelnummer exakt
    if article_number:
        match = base_q.filter(SupplierPriceEntry.article_number == article_number).first()
        if match:
            how = f"Artikelnummer {article_number}"
            confidence = 1.0

    # b) Produktname + Hersteller exakt
    if match is None and manufacturer:
        candidates = base_q.filter(
            SupplierPriceEntry.manufacturer == manufacturer,
        ).all()
        for c in candidates:
            if _norm(c.product_name) == _norm(material_name):
                match = c
                how = f"Name+Hersteller exakt ({manufacturer})"
                confidence = 0.95
                break

    # c) Fuzzy auf Produktname + Einheit (ggf. + Hersteller)
    # Seit B+4.2.5: der asymmetrische Normalizer scored sehr aggressiv auf
    # Token-Coverage; deshalb ziehen wir den manufacturer-Filter auch hier
    # durch, sobald ein Hersteller in der Query bekannt ist.
    # Seit B+4.2.6: der Unit-Filter ist tolerant — "m" und "lfm" sind
    # z. B. gleichwertig. Da das DB-seitig nicht praktikabel ist (keine
    # Funktion in SQL), fischen wir die mfr-gefilterten Kandidaten und
    # filtern die Einheit anschliessend in Python via unit_matches().
    if match is None:
        from app.services.unit_normalizer import unit_matches

        cand_q = base_q
        if manufacturer:
            cand_q = cand_q.filter(SupplierPriceEntry.manufacturer == manufacturer)
        all_mfr_candidates = cand_q.all()
        candidates = [
            c for c in all_mfr_candidates
            if unit_matches(unit, c.unit) or unit_matches(unit, c.effective_unit)
        ]
        # B+4.2.6 Option C Phase 2: Blacklist-Pre-Filter vor dem Scoring.
        # Kandidaten mit `attributes.product_code_type` in PRODUCT_CODE_BLACKLIST
        # und Dimension-Kollision mit der Query werden hier ausgeschlossen,
        # bevor der Fuzzy-Scorer sie zufällig als Gewinner wählt. Loest die
        # PE-Folie-UT40-Regression aus dem E2E-Lauf vom 21.04.2026.
        candidates = [
            c for c in candidates
            if not should_exclude_by_blacklist(c.attributes, material_name)
        ]
        best, ratio = _best_fuzzy(candidates, material_name, lambda e: e.product_name)
        if best is not None and ratio >= FUZZY_MATCH_THRESHOLD:
            match = best
            how = f"Fuzzy ({ratio:.2f}) auf Produktname + Einheit ~{unit}"
            confidence = ratio

    if match is None:
        details.append({"stage": "supplier_price", "matched": False, "active_lists": len(active_lists)})
        return None

    # Finde zugehörige Pricelist (für supplier_name + Rabatt-Zuordnung)
    parent = next((pl for pl in active_lists if pl.id == match.pricelist_id), None)
    supplier_name = parent.supplier_name if parent else None

    # Rabatt-Regel?
    discount_rule = _find_discount_rule(
        db=db,
        tenant_id=tenant_id,
        supplier_name=supplier_name,
        category=match.category,
        today=today,
    )

    # B+4.2.7: wenn der Entry eine abweichende `effective_unit` traegt
    # (z. B. Karton-Preis wurde auf Stueckpreis entpackt), nehmen wir den
    # effektiven Preis + die effektive Einheit als Basis. Andernfalls
    # bleibt alles wie bisher (price_net + unit).
    use_effective = (
        match.effective_unit
        and match.effective_unit != match.unit
        and match.price_per_effective_unit is not None
    )
    if use_effective:
        original = Decimal(str(match.price_per_effective_unit))
        result_unit = match.effective_unit
    else:
        original = Decimal(str(match.price_net))
        result_unit = match.unit

    if discount_rule is not None:
        factor = Decimal("1") - (Decimal(str(discount_rule.discount_percent)) / Decimal("100"))
        final_price = original * factor
        disc_pct = Decimal(str(discount_rule.discount_percent))
        desc = (
            f"{supplier_name}-Listenpreis, -{disc_pct}% Rabatt "
            f"(Regel: {discount_rule.category or 'alle Kategorien'})"
        )
    else:
        final_price = original
        disc_pct = None
        desc = f"{supplier_name}-Listenpreis ({how})"

    details.append(
        {
            "stage": "supplier_price",
            "matched": True,
            "match_criterion": how,
            "supplier": supplier_name,
            "discount_applied": disc_pct is not None,
            "used_effective_unit": use_effective,
        }
    )

    return PriceLookupResult(
        price=final_price.quantize(Decimal("0.0001")),
        currency=match.currency or "EUR",
        unit=result_unit,
        price_source="supplier_price",
        source_description=desc,
        original_price=original,
        applied_discount_percent=disc_pct,
        supplier_name=supplier_name,
        pricelist_id=match.pricelist_id,
        entry_id=match.id,
        match_confidence=confidence,
        needs_review=bool(match.needs_review) or confidence < FUZZY_MATCH_THRESHOLD,
    )


def _try_legacy_price(
    *,
    db: Session,
    tenant_id: str,
    material_name: str,
    unit: str,
    manufacturer: str | None,
    category: str | None,
    details: list[dict],
) -> PriceLookupResult | None:
    """Stufe 3 — bestehende PriceEntry-Infrastruktur (Backward-Compat)."""
    # Late import: vermeidet zirkuläre Abhängigkeit bei Model-Loading.
    from app.models.price_entry import PriceEntry
    from app.models.price_list import PriceList

    q = (
        db.query(PriceEntry)
        .join(PriceList, PriceEntry.price_list_id == PriceList.id)
        .filter(
            PriceList.tenant_id == tenant_id,
            PriceList.aktiv.is_(True),
        )
    )
    candidates = q.all()
    if not candidates:
        details.append({"stage": "legacy_price", "matched": False, "reason": "keine aktive Legacy-Liste"})
        return None

    # B+4.2.6: Einheiten-Filter tolerant (SQL kann unit_matches nicht; in
    # Python nachfiltern). Nur anwenden, wenn die Query eine Einheit traegt.
    if unit:
        from app.services.unit_normalizer import unit_matches
        candidates = [
            c for c in candidates
            if unit_matches(unit, c.basis_einheit) or unit_matches(unit, c.einheit)
        ]
        if not candidates:
            details.append({"stage": "legacy_price", "matched": False, "reason": f"keine Kandidaten mit Einheit ~{unit}"})
            return None

    best, ratio = _best_fuzzy(candidates, material_name, lambda e: e.produktname)
    if best is None or ratio < FUZZY_MATCH_THRESHOLD:
        details.append(
            {
                "stage": "legacy_price",
                "matched": False,
                "best_ratio": round(ratio, 3),
            }
        )
        return None

    price = Decimal(str(best.preis_pro_basis or best.preis))
    details.append(
        {
            "stage": "legacy_price",
            "matched": True,
            "match_criterion": f"Fuzzy ({ratio:.2f}) auf Legacy-Produktname",
        }
    )
    return PriceLookupResult(
        price=price.quantize(Decimal("0.0001")),
        currency="EUR",
        unit=best.basis_einheit or best.einheit or unit,
        price_source="legacy_price",
        source_description=f"Legacy-Preisliste: {best.hersteller} {best.produktname}".strip(),
        original_price=price,
        applied_discount_percent=None,
        supplier_name=best.hersteller or None,
        pricelist_id=best.price_list_id,
        entry_id=best.id,
        match_confidence=ratio,
        needs_review=ratio < 0.95,
    )


def _try_estimate(
    *,
    db: Session,
    tenant_id: str,
    unit: str,
    category: str | None,
    today: date,
    details: list[dict],
) -> PriceLookupResult | None:
    """Stufe 4 — Schätzung aus Ø Preis der letzten 12 Monate für Kategorie+Einheit."""
    if not category:
        details.append({"stage": "estimated", "matched": False, "reason": "Kategorie fehlt"})
        return None

    year_ago = today - timedelta(days=365)
    q = (
        db.query(SupplierPriceEntry)
        .join(SupplierPriceList, SupplierPriceEntry.pricelist_id == SupplierPriceList.id)
        .filter(
            SupplierPriceEntry.tenant_id == tenant_id,
            SupplierPriceEntry.category == category,
            SupplierPriceList.valid_from >= year_ago,
            or_(
                SupplierPriceEntry.unit == unit,
                SupplierPriceEntry.effective_unit == unit,
            ),
        )
    )
    rows = q.all()
    if not rows:
        details.append(
            {
                "stage": "estimated",
                "matched": False,
                "category": category,
                "unit": unit,
            }
        )
        return None

    # Ø über price_per_effective_unit bei effective_unit-Match, sonst price_net
    prices: list[float] = []
    for r in rows:
        if r.effective_unit == unit:
            prices.append(r.price_per_effective_unit)
        else:
            prices.append(r.price_net)
    avg = sum(prices) / len(prices)
    details.append(
        {
            "stage": "estimated",
            "matched": True,
            "samples": len(prices),
            "category": category,
            "unit": unit,
        }
    )
    return PriceLookupResult(
        price=Decimal(str(avg)).quantize(Decimal("0.0001")),
        currency="EUR",
        unit=unit,
        price_source="estimated",
        source_description=f"Ø {len(prices)} Einträge in Kategorie '{category}' der letzten 12 Monate",
        original_price=None,
        applied_discount_percent=None,
        match_confidence=0.5,
        needs_review=True,
    )


# ---------------------------------------------------------------------------
# B+4.3.0b — Candidates-Endpoint-Support (Variante 2: alle Materialien)
# ---------------------------------------------------------------------------
def list_candidates_for_position(
    *,
    db: Session,
    tenant_id: str,
    erkanntes_system: str | None,
    feuerwiderstand: str | None = None,
    plattentyp: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """Liefert pro Material der Position eine Top-N + estimated-Liste.

    Nutzt das bestehende Rezept-System (`resolve_rezept`) zur Ermittlung
    der Materialien und die Stage-2c-Mechanik (Unit-Match,
    Blacklist-Filter, Fuzzy-Scoring) zur Bewertung aller Kandidaten.

    Rueckgabe: Liste von Dicts mit Form
        {material_name, required_amount, unit, candidates}
    Der Caller mappt auf :class:`MaterialWithCandidates`.

    Null-safe: wenn das Rezept nicht aufloesbar ist oder keine
    Materialien hat, wird eine leere Liste zurueckgegeben.
    """
    from app.services.material_normalizer import score_query_against_candidate
    from app.services.materialrezepte import resolve_rezept
    from app.services.unit_normalizer import unit_matches

    if not erkanntes_system:
        return []
    rezept = resolve_rezept(
        erkanntes_system, feuerwiderstand or "", plattentyp or ""
    )
    if not rezept or not rezept.materialien:
        return []

    # Alle aktiven Pricelists einmalig laden (fuer supplier_name-Mapping).
    active_lists = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.tenant_id == tenant_id,
            SupplierPriceList.is_active.is_(True),
            SupplierPriceList.status != PricelistStatus.ARCHIVED.value,
        )
        .all()
    )
    list_by_id = {pl.id: pl for pl in active_lists}
    active_ids = list(list_by_id.keys())

    # Alle Entries aller aktiven Listen — einmalig laden, danach pro
    # Material filtern (spart Roundtrips).
    all_entries: list[SupplierPriceEntry] = []
    if active_ids:
        all_entries = (
            db.query(SupplierPriceEntry)
            .filter(
                SupplierPriceEntry.tenant_id == tenant_id,
                SupplierPriceEntry.pricelist_id.in_(active_ids),
            )
            .all()
        )

    results: list[dict] = []
    for mb in rezept.materialien:
        parts = _dna_parts(mb.dna_pattern)
        material_name = " ".join(
            p for p in (parts["produktname"], parts["abmessungen"], parts["variante"]) if p
        ).strip() or parts["produktname"] or ""
        query_unit = mb.basis_einheit or ""
        query_manufacturer = parts["hersteller"] or None
        query_category = parts["kategorie"] or None

        # Pool pro Material filtern: Unit-Match + Blacklist
        pool = [
            e for e in all_entries
            if (unit_matches(query_unit, e.unit) or unit_matches(query_unit, e.effective_unit))
            and not should_exclude_by_blacklist(e.attributes, material_name)
        ]

        scored: list[tuple[SupplierPriceEntry, float]] = []
        for e in pool:
            score_pct = score_query_against_candidate(material_name, e.product_name or "")
            score = score_pct / 100.0
            scored.append((e, score))
        # Sortierung: hoechster Score zuerst
        scored.sort(key=lambda s: -s[1])

        # Top-N echte Kandidaten
        top = scored[:limit]
        candidates: list[dict] = []
        for e, score in top:
            if score <= 0.0:
                continue  # reine Noise-Treffer rauslassen
            pl = list_by_id.get(e.pricelist_id)
            supplier = (pl.supplier_name if pl else "") or ""
            list_name = (pl.list_name if pl else "") or ""
            pricelist_name = (
                f"{supplier} — {list_name}" if (supplier and list_name) else (supplier or list_name or "—")
            )
            stage = "supplier_price" if score >= FUZZY_MATCH_THRESHOLD else "fuzzy"
            # price + unit aus effektivem Einzelpreis, wenn vorhanden
            if e.effective_unit and e.price_per_effective_unit is not None:
                price_out = float(e.price_per_effective_unit)
                unit_out = e.effective_unit
            else:
                price_out = float(e.price_net)
                unit_out = e.unit or ""
            match_reason = f"Fuzzy-Aehnlichkeit {score*100:.0f}%"
            candidates.append({
                "pricelist_name": pricelist_name,
                "candidate_name": e.product_name or "",
                "match_confidence": round(score, 3),
                "stage": stage,
                "price_net": price_out,
                "unit": unit_out,
                "match_reason": match_reason,
            })

        # Virtueller Estimated-Eintrag — immer, auch wenn supplier_price-
        # Matches existieren (Design-Entscheidung d). Wenn kein Kategorie-
        # Durchschnitt berechenbar ist (fehlende Datenbasis), wird ein
        # Platzhalter-Eintrag mit Preis 0 zurueckgegeben, damit die
        # Invariante "letzter Eintrag = estimated" erhalten bleibt.
        estimated = _build_estimated_candidate(
            db=db,
            tenant_id=tenant_id,
            category=query_category,
            unit=query_unit,
        )
        if estimated is None:
            estimated = {
                "pricelist_name": "(Schaetzung)",
                "candidate_name": f"O Kategorie {query_category or '?'}",
                "match_confidence": 0.0,
                "stage": "estimated",
                "price_net": 0.0,
                "unit": query_unit or "",
                "match_reason": "Kein Katalog-Durchschnitt verfuegbar",
            }
        candidates.append(estimated)

        results.append({
            "material_name": material_name,
            "required_amount": float(mb.menge_pro_einheit),
            "unit": query_unit,
            "candidates": candidates,
        })
    return results


def _dna_parts(pattern: str) -> dict[str, str]:
    """Zerlegt DNA-Pattern in die fuenf Felder.

    Duplikat aus kalkulation._parse_dna_pattern — bewusst lokal
    gehalten, damit price_lookup nicht auf kalkulation importiert.
    """
    parts = (pattern or "").split("|")
    keys = ["hersteller", "kategorie", "produktname", "abmessungen", "variante"]
    out = {k: "" for k in keys}
    for k, v in zip(keys, parts, strict=False):
        out[k] = v.strip()
    return out


def _build_estimated_candidate(
    *,
    db: Session,
    tenant_id: str,
    category: str | None,
    unit: str | None,
) -> dict | None:
    """Erzeugt den virtuellen Kategorie-Mittelwert-Kandidaten.

    Analog zu `_try_estimate`, aber liefert ein Dict fuer die Kandidaten-
    Liste statt ein PriceLookupResult. Nutzt toleranten Unit-Match
    (`unit_matches` aus unit_normalizer) — sonst wuerde eine lfm-Query
    keinen Durchschnitt aus m-Entries bekommen.
    """
    if not category or not unit:
        return None
    from app.services.unit_normalizer import unit_matches

    today = date.today()
    year_ago = today - timedelta(days=365)
    rows = (
        db.query(SupplierPriceEntry)
        .join(SupplierPriceList, SupplierPriceEntry.pricelist_id == SupplierPriceList.id)
        .filter(
            SupplierPriceEntry.tenant_id == tenant_id,
            SupplierPriceEntry.category == category,
            SupplierPriceList.valid_from >= year_ago,
        )
        .all()
    )
    prices: list[float] = []
    for r in rows:
        if unit_matches(unit, r.effective_unit) and r.price_per_effective_unit is not None:
            prices.append(float(r.price_per_effective_unit))
        elif unit_matches(unit, r.unit):
            prices.append(float(r.price_net))
    if not prices:
        return None
    avg = sum(prices) / len(prices)
    return {
        "pricelist_name": "(Schaetzung)",
        "candidate_name": f"O Kategorie {category}",
        "match_confidence": 0.5,
        "stage": "estimated",
        "price_net": round(avg, 4),
        "unit": unit,
        "match_reason": f"O aus Kategorie {category} ({len(prices)} Eintraege, 12 Monate)",
    }


# ---------------------------------------------------------------------------
# Rabatt-Regel
# ---------------------------------------------------------------------------
def _find_discount_rule(
    *,
    db: Session,
    tenant_id: str,
    supplier_name: str | None,
    category: str | None,
    today: date,
) -> TenantDiscountRule | None:
    """Sucht die anwendbare Rabatt-Regel.

    Matching-Regeln:
    - supplier_name MUSS matchen
    - Regel mit Kategorie-Filter greift nur wenn die gleiche Kategorie vorliegt
    - Gültigkeitszeitraum muss passen
    - Bei mehreren: Spezifischere Regel (mit Kategorie) gewinnt vor Wildcard
    """
    if not supplier_name:
        return None

    q = db.query(TenantDiscountRule).filter(
        TenantDiscountRule.tenant_id == tenant_id,
        TenantDiscountRule.supplier_name == supplier_name,
        TenantDiscountRule.valid_from <= today,
        or_(
            TenantDiscountRule.valid_until.is_(None),
            TenantDiscountRule.valid_until >= today,
        ),
    )
    rules = q.all()
    if not rules:
        return None

    # Spezifische Regel (category matcht) hat Vorrang vor Wildcard (category=None)
    specific = [r for r in rules if r.category and r.category == category]
    if specific:
        return specific[0]
    wildcard = [r for r in rules if r.category is None]
    if wildcard:
        return wildcard[0]
    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _best_fuzzy(items, target: str, key_fn):
    """Gibt (best_item, best_ratio) zurück. Items leer -> (None, 0.0).

    Seit B+4.2.5 nutzt diese Funktion die asymmetrische Token-Coverage
    aus material_normalizer, die speziell fuer "kurze Anfrage vs. langer
    realer Produktname" getuned ist. Der Score bleibt in [0, 1]-Skalierung,
    damit aufrufende Stellen den Schwellenvergleich nicht anfassen muessen.

    Fallback: Wenn material_normalizer aus irgendeinem Grund nicht
    importiert werden kann, nutzen wir stdlib SequenceMatcher wie zuvor.
    """
    best = None
    best_ratio = 0.0
    target_norm = _norm(target)
    if not target_norm:
        return None, 0.0
    try:
        from app.services.material_normalizer import score_query_against_candidate
        _use_normalizer = True
    except ImportError:  # pragma: no cover
        _use_normalizer = False
    for it in items:
        raw_candidate = key_fn(it)
        if not raw_candidate:
            continue
        if _use_normalizer:
            score_pct = score_query_against_candidate(target, raw_candidate)
            r = score_pct / 100.0
        else:
            r = SequenceMatcher(None, target_norm, _norm(raw_candidate)).ratio()
        if r > best_ratio:
            best_ratio = r
            best = it
    return best, best_ratio


def _pick_best_name_match(candidates, target: str, _ignored_key_fn):
    """Override-Variante: nimm den Kandidaten mit besten Namen-Match (auf notes)
    oder als Fallback den ersten. Overrides sind über article_number primär
    gematcht, dies ist nur der Hersteller/Einheit-Fallback."""
    if not candidates:
        return None
    # Overrides haben kein product_name-Feld, fallen zurück auf article_number
    # als grobes Signal oder einfach ersten treffer.
    return candidates[0]
