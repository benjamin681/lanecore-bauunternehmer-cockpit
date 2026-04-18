"""DNA-Matcher: LV-Materialrezept → Kunden-Preisliste → günstigster Preis."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy.orm import Session

from app.models.price_entry import PriceEntry
from app.models.price_list import PriceList

log = structlog.get_logger()


@dataclass
class MatchResult:
    price_entry: PriceEntry | None
    preis_pro_basis: float
    basis_einheit: str
    konfidenz: float           # 1.0 exakter Match, 0.7 fuzzy, 0.0 kein Match
    begruendung: str


def _parse_pattern(pattern: str) -> dict[str, str]:
    parts = pattern.split("|")
    keys = ["hersteller", "kategorie", "produktname", "abmessungen", "variante"]
    out: dict[str, str] = {}
    for k, v in zip(keys, parts, strict=False):
        out[k] = v.strip()
    return out


def _score_entry(entry: PriceEntry, pattern_parts: dict[str, str]) -> float:
    """Score 0.0 - 1.0 wie gut das Entry zum Pattern passt."""
    score = 0.0
    weight_total = 0.0
    weights = {"kategorie": 3, "produktname": 3, "abmessungen": 3, "hersteller": 1, "variante": 1}

    for key, w in weights.items():
        wanted = pattern_parts.get(key, "").lower()
        have = getattr(entry, key, "").lower()
        if not wanted:
            # Pattern ist leer → egal
            weight_total += w * 0.5  # leichter Bonus für nicht-gefordert
            score += w * 0.5
            continue
        weight_total += w
        # Exakter Match
        if wanted == have:
            score += w
            continue
        # Substring-Match
        if wanted in have or have in wanted:
            score += w * 0.8
            continue
        # Token-Match (einzelne Wörter)
        wanted_tokens = set(wanted.replace("-", " ").split())
        have_tokens = set(have.replace("-", " ").split())
        if wanted_tokens & have_tokens:
            score += w * 0.5
    if weight_total == 0:
        return 0.0
    return score / weight_total


def find_best_match(
    *,
    db: Session,
    tenant_id: str,
    price_list_id: str,
    dna_pattern: str,
) -> MatchResult:
    """Sucht in der Kundenpreisliste nach dem besten Treffer."""
    pattern_parts = _parse_pattern(dna_pattern)

    # Grobfilter: nur Einträge aus dieser Preisliste
    candidates = (
        db.query(PriceEntry)
        .join(PriceList, PriceEntry.price_list_id == PriceList.id)
        .filter(
            PriceList.id == price_list_id,
            PriceList.tenant_id == tenant_id,
        )
        .all()
    )

    if not candidates:
        return MatchResult(
            price_entry=None,
            preis_pro_basis=0.0,
            basis_einheit="",
            konfidenz=0.0,
            begruendung="Keine Preisliste hinterlegt",
        )

    # Falls Kategorie im Pattern → vorfiltern
    cat_wanted = pattern_parts.get("kategorie", "").lower()
    if cat_wanted:
        filtered = [c for c in candidates if cat_wanted in c.kategorie.lower()]
        if filtered:
            candidates = filtered

    scored = [(c, _score_entry(c, pattern_parts)) for c in candidates]
    scored.sort(key=lambda t: (-t[1], t[0].preis_pro_basis))  # höchster Score, dann günstigster

    best, score = scored[0]
    if score < 0.5:
        return MatchResult(
            price_entry=None,
            preis_pro_basis=0.0,
            basis_einheit="",
            konfidenz=score,
            begruendung=f"Kein passender Eintrag (Best-Score {score:.2f})",
        )

    return MatchResult(
        price_entry=best,
        preis_pro_basis=best.preis_pro_basis,
        basis_einheit=best.basis_einheit,
        konfidenz=score,
        begruendung=f"Match: {best.hersteller} {best.produktname} {best.abmessungen}",
    )
