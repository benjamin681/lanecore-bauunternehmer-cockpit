"""Service-Layer fuer manuelle Korrekturen an SupplierPriceEntries.

Nutzer korrigiert ueber das Review-UI einen einzelnen Preislisten-Eintrag
(z.B. fehlende Bundgroesse). Diese Korrektur wird auf zwei Ebenen wirksam:

1. SOFORT: der betroffene SupplierPriceEntry wird aktualisiert
   (pieces_per_package/package_size/price_per_effective_unit/unit, je
   nach Korrektur-Typ) und needs_review=False gesetzt. Die Pricelist-
   `entries_reviewed`-Counter wird synchronisiert.

2. PERSISTENT (optional): die Korrektur wird in
   `lvp_product_corrections` abgelegt. Beim naechsten Upload derselben
   Preisliste (oder einer anderen Preisliste mit identischem
   manufacturer+article_number) wendet der Parser die Korrektur
   automatisch an (siehe pricelist_parser.py / apply_known_corrections).

Der Service kapselt:
- Validierung des corrected_value je Korrektur-Typ.
- Anwendung der Felder auf den Entry.
- Upsert in die Korrekturen-Tabelle (UniqueConstraint greift ab PG15).
- Audit-Tracking: correction_applied=True, reviewed_by/at.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.pricing import (
    ProductCorrection,
    ProductCorrectionType,
    SupplierPriceEntry,
    SupplierPriceList,
)


class CorrectionValidationError(ValueError):
    """Wird geworfen, wenn corrected_value fuer den gewaehlten Typ ungueltig ist."""


# --------------------------------------------------------------------------- #
# Validierung pro Korrektur-Typ
# --------------------------------------------------------------------------- #
def _validate_corrected_value(correction_type: str, value: dict[str, Any]) -> None:
    """Raises CorrectionValidationError wenn der Payload unplausibel ist."""
    if correction_type == ProductCorrectionType.PIECES_PER_PACKAGE.value:
        pieces = value.get("pieces_per_package")
        if not isinstance(pieces, int) or pieces <= 0:
            raise CorrectionValidationError(
                "pieces_per_package muss positive Ganzzahl sein"
            )
    elif correction_type == ProductCorrectionType.UNIT_OVERRIDE.value:
        unit = value.get("unit")
        if not isinstance(unit, str) or not unit.strip():
            raise CorrectionValidationError("unit muss nicht-leerer String sein")
        size = value.get("package_size")
        if size is not None and (not isinstance(size, (int, float)) or size <= 0):
            raise CorrectionValidationError(
                "package_size muss positiv sein wenn angegeben"
            )
    elif correction_type == ProductCorrectionType.PRICE_PER_EFFECTIVE_UNIT.value:
        ppeu = value.get("price_per_effective_unit")
        if not isinstance(ppeu, (int, float)) or ppeu <= 0:
            raise CorrectionValidationError(
                "price_per_effective_unit muss positiv sein"
            )
    elif correction_type == ProductCorrectionType.CONFIRMED_AS_IS.value:
        # Akzeptiert leeren Dict oder zumindest keine zwingenden Felder
        pass
    else:
        raise CorrectionValidationError(
            f"Unbekannter correction_type: {correction_type}"
        )


# --------------------------------------------------------------------------- #
# Anwendung auf Entry
# --------------------------------------------------------------------------- #
def apply_correction_to_entry(
    entry: SupplierPriceEntry,
    correction_type: str,
    corrected_value: dict[str, Any],
    user_id: str,
) -> None:
    """Mutiert Entry in-place. Ruft den Caller, der commit() macht."""
    _validate_corrected_value(correction_type, corrected_value)

    if correction_type == ProductCorrectionType.PIECES_PER_PACKAGE.value:
        pieces = int(corrected_value["pieces_per_package"])
        entry.pieces_per_package = pieces
        # Preis pro effektive Einheit neu berechnen — nur sinnvoll wenn
        # package_size schon bekannt ist (z.B. Laenge in Metern aus der
        # PDF-Zeile). Sonst bleibt price_per_effective_unit gleich und der
        # User muss zusaetzlich UNIT_OVERRIDE setzen.
        if entry.package_size and entry.package_size > 0:
            effective_total = entry.package_size * pieces
            if effective_total > 0:
                entry.price_per_effective_unit = entry.price_net / effective_total

    elif correction_type == ProductCorrectionType.UNIT_OVERRIDE.value:
        entry.unit = corrected_value["unit"][:50]
        if "package_size" in corrected_value and corrected_value["package_size"]:
            entry.package_size = float(corrected_value["package_size"])
        if corrected_value.get("effective_unit"):
            entry.effective_unit = corrected_value["effective_unit"][:50]
        # ppeu nachziehen, wenn package_size + pieces_per_package bekannt
        if entry.package_size and entry.pieces_per_package:
            total = entry.package_size * entry.pieces_per_package
            if total > 0:
                entry.price_per_effective_unit = entry.price_net / total

    elif correction_type == ProductCorrectionType.PRICE_PER_EFFECTIVE_UNIT.value:
        entry.price_per_effective_unit = float(
            corrected_value["price_per_effective_unit"]
        )
        if corrected_value.get("effective_unit"):
            entry.effective_unit = corrected_value["effective_unit"][:50]

    elif correction_type == ProductCorrectionType.CONFIRMED_AS_IS.value:
        # Kein Feld-Update, nur Review-Flags werden unten gesetzt.
        pass

    # Review-Flags setzen
    entry.needs_review = False
    entry.correction_applied = True
    entry.reviewed_by_user_id = user_id
    entry.reviewed_at = datetime.now(UTC)

    # review_reason in attributes archivieren (nicht loeschen) als
    # review_reason_resolved — das UI kann damit anzeigen, warum der
    # Eintrag urspruenglich geflagged war.
    attrs = dict(entry.attributes or {})
    if "review_reason" in attrs:
        attrs["review_reason_resolved"] = attrs.pop("review_reason")
    attrs["correction_source"] = "manual_user_input"
    attrs["correction_type"] = correction_type
    entry.attributes = attrs


# --------------------------------------------------------------------------- #
# Persistenz in lvp_product_corrections (Upsert)
# --------------------------------------------------------------------------- #
def upsert_product_correction(
    db: Session,
    tenant_id: str,
    entry: SupplierPriceEntry,
    correction_type: str,
    corrected_value: dict[str, Any],
    user_id: str,
) -> ProductCorrection:
    """Upsert: bei gleichem Key den bestehenden Eintrag ueberschreiben."""
    existing = (
        db.query(ProductCorrection)
        .filter(
            and_(
                ProductCorrection.tenant_id == tenant_id,
                ProductCorrection.manufacturer.is_(entry.manufacturer)
                if entry.manufacturer is None
                else ProductCorrection.manufacturer == entry.manufacturer,
                ProductCorrection.article_number.is_(entry.article_number)
                if entry.article_number is None
                else ProductCorrection.article_number == entry.article_number,
                ProductCorrection.correction_type == correction_type,
            )
        )
        .first()
    )
    now = datetime.now(UTC)
    if existing is not None:
        existing.corrected_value = corrected_value
        existing.product_name_fallback = entry.product_name
        existing.updated_at = now
        return existing

    correction = ProductCorrection(
        tenant_id=tenant_id,
        manufacturer=entry.manufacturer,
        article_number=entry.article_number,
        product_name_fallback=entry.product_name,
        correction_type=correction_type,
        corrected_value=corrected_value,
        created_by_user_id=user_id,
    )
    db.add(correction)
    return correction


# --------------------------------------------------------------------------- #
# Counter-Sync auf Pricelist
# --------------------------------------------------------------------------- #
def bump_reviewed_counter(pl: SupplierPriceList) -> None:
    """Wird nach einer ``True -> False``-Transition von needs_review aufgerufen."""
    pl.entries_reviewed = (pl.entries_reviewed or 0) + 1


# --------------------------------------------------------------------------- #
# Lookup fuer Parser-Hook
# --------------------------------------------------------------------------- #
def find_applicable_corrections(
    db: Session,
    tenant_id: str,
    manufacturer: str | None,
    article_number: str | None,
    product_name: str | None,
) -> list[ProductCorrection]:
    """Holt alle Korrekturen fuer ein Produkt.

    Strategie:
    1. Bevorzugt: (manufacturer, article_number) match — eindeutigster Key.
    2. Fallback: product_name gleich product_name_fallback — schwaecherer
       Match, nur wenn Artikelnr unbekannt.

    Rueckgabe: Liste aller Korrekturen, eine pro correction_type (durch
    UniqueConstraint garantiert).
    """
    if article_number:
        q = db.query(ProductCorrection).filter(
            ProductCorrection.tenant_id == tenant_id,
            ProductCorrection.article_number == article_number,
        )
        if manufacturer:
            q = q.filter(ProductCorrection.manufacturer == manufacturer)
        results = q.all()
        if results:
            return results

    # Fallback ueber product_name
    if product_name:
        return (
            db.query(ProductCorrection)
            .filter(
                ProductCorrection.tenant_id == tenant_id,
                ProductCorrection.article_number.is_(None),
                ProductCorrection.product_name_fallback == product_name,
            )
            .all()
        )
    return []


# --------------------------------------------------------------------------- #
# Parser-Hook: bekannte Korrekturen auf frisch geparste Entries anwenden
# --------------------------------------------------------------------------- #
def apply_known_corrections_to_entries(
    db: Session,
    tenant_id: str,
    entries: list[SupplierPriceEntry],
) -> int:
    """Wendet alle bekannten Korrekturen auf eine Liste Entries an.

    Aufgerufen vom Parser NACH Parse + Backfill, VOR dem finalen commit.
    Gibt die Anzahl der modifizierten Entries zurueck (fuer Logging).
    """
    if not entries:
        return 0

    modified = 0
    for entry in entries:
        corrections = find_applicable_corrections(
            db=db,
            tenant_id=tenant_id,
            manufacturer=entry.manufacturer,
            article_number=entry.article_number,
            product_name=entry.product_name,
        )
        if not corrections:
            continue
        for correction in corrections:
            try:
                apply_correction_to_entry(
                    entry=entry,
                    correction_type=correction.correction_type,
                    corrected_value=correction.corrected_value or {},
                    user_id=correction.created_by_user_id,
                )
            except CorrectionValidationError:
                # Korrigierten Wert, der urspruenglich gueltig war, halten
                # wir fuer einen Edge-Case (Schema-Drift). Ueberspringen und
                # Entry bleibt im Originalzustand.
                continue
        modified += 1
    return modified
