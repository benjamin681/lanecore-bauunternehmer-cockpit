"""Parser: Händler-Preisliste-PDF → Produkt-DNA-Einträge."""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.models.price_entry import PriceEntry
from app.models.price_list import PriceList
from app.services.claude_client import claude
from app.services.pdf_utils import compute_sha256, pdf_to_page_images, save_upload

log = structlog.get_logger()

SYSTEM_PROMPT = """Du bist Experte für Trockenbau-Materialien und Händler-Preislisten.

Du bekommst Bilder einer Händler-Preisliste (z.B. Kemmler, Wölpert, Raab Karcher).
Extrahiere JEDEN erkennbaren Preis-Eintrag als strukturierten JSON-Datensatz.

AUSGABEFORMAT (strikt):
{
  "eintraege": [
    {
      "art_nr": "3530100012",           // Artikelnummer wenn erkennbar, sonst ""
      "hersteller": "Knauf",             // z.B. "Knauf", "Siniat", "Rockwool", "Upmann", "OWA"
      "kategorie": "Gipskarton",         // "Gipskarton" | "Dämmung" | "Profile" | "Schrauben" | "Spachtel" | "Revisionsklappen" | "Klebeband" | "Putz" | "Estrich" | "Farbe" | "Bauchemie" | "Werkzeug" | "Aquapanel" | "Sonstiges"
      "produktname": "GKB Standard",     // Hauptname ohne Abmessung (z.B. "GKB", "GKF", "Diamant", "Fireboard", "Silentboard", "Sonorock")
      "abmessungen": "12.5mm",           // Maßangabe: "12.5mm" oder "40mm" oder "2000x1250" oder "CW75x0.6"
      "variante": "",                    // z.B. "Imprägniert", "Feuerschutz", "Einmannplatte", sonst ""
      "preis": 3.00,                     // Zahl (Punkt als Dezimaltrennzeichen)
      "einheit": "€/m²",                 // "€/m²" | "€/lfm" | "€/Stk" | "€/kg" | "€/Paket (500 Stk)"
      "konfidenz": 0.95                  // 0.0-1.0, niedriger wenn unklar
    }
  ]
}

PRODUKT-DNA-REGEL: Die Kombination Hersteller | Kategorie | Produktname | Abmessungen | Variante muss EINDEUTIG sein.
Wenn derselbe Artikel mehrfach vorkommt (verschiedene Liste A/B-Preise), gib ihn nur EINMAL mit dem niedrigsten Preis zurück.
Bei Unsicherheit: konfidenz < 0.85 setzen und in variante oder produktname den Originaltext erhalten.

ANTWORTE AUSSCHLIESSLICH MIT JSON. KEIN Fließtext.
"""


def _normalize_to_base(
    preis: float,
    einheit: str,
    variante: str = "",
    abmessungen: str = "",
) -> tuple[float, str]:
    """Normalisiert "€/Paket (500 Stk)" → €/Stk, "€/Bd. (16 St./Bd., BL=3m)" → €/lfm, …

    Berücksichtigt neben `einheit` auch freitext-Hinweise in variante und abmessungen,
    weil Händler oft dort "16 St./Bd., BL=3000mm" schreiben.
    """
    import re

    e = einheit.lower().strip()
    context = f"{einheit} {variante} {abmessungen}".lower()

    # Gebinde-Erkennung: "16 St./Bd." + "BL=3000mm" → Preis pro lfm
    m_pkg = re.search(r"(\d+)\s*(?:st|stk)\.?\s*/\s*(?:bd|pak|pkt|paket|bund)", context)
    m_bl = re.search(r"bl\s*=?\s*(\d+[\.,]?\d*)\s*(mm|cm|m)\b", context)
    if m_pkg and m_bl:
        stueck = int(m_pkg.group(1))
        wert = float(m_bl.group(1).replace(",", "."))
        unit = m_bl.group(2)
        lfm_pro_stk = wert / {"mm": 1000, "cm": 100, "m": 1}[unit]
        total_lfm = stueck * lfm_pro_stk
        if total_lfm > 0:
            return round(preis / total_lfm, 4), "lfm"

    # "Paket (500 Stk)"
    m_pkg_only = re.search(r"(\d+)\s*stk", context)
    if ("paket" in e or "bd" in e or "bund" in e or "(" in e) and m_pkg_only:
        n = int(m_pkg_only.group(1))
        if n > 0:
            return round(preis / n, 4), "Stk"

    if "m²" in e or "qm" in e or "m2" in e:
        return preis, "m²"
    if "lfm" in e or e.endswith("/m") or re.search(r"€\s*/\s*m(?!\w)", e):
        return preis, "lfm"
    if "stk" in e:
        return preis, "Stk"
    if "kg" in e:
        return preis, "kg"
    if "liter" in e or "/l" in e:
        return preis, "l"
    return preis, einheit[:20] if einheit else ""


def build_dna(hersteller: str, kategorie: str, produktname: str, abmessungen: str, variante: str) -> str:
    """DNA-String: Hersteller|Kategorie|Produktname|Abmessungen|Variante."""
    parts = [hersteller, kategorie, produktname, abmessungen, variante]
    return "|".join(p.strip() for p in parts)


def parse_and_store(
    *,
    db: Session,
    tenant_id: str,
    pdf_bytes: bytes,
    original_dateiname: str,
    haendler: str,
    niederlassung: str = "",
    stand_monat: str = "",
) -> PriceList:
    """
    Parst eine Preisliste per Claude Vision und speichert als PriceList + PriceEntries.

    Returns:
        PriceList im Status "review"
    """
    from app.core.config import settings

    sha = compute_sha256(pdf_bytes)

    pl = PriceList(
        tenant_id=tenant_id,
        haendler=haendler,
        niederlassung=niederlassung,
        stand_monat=stand_monat,
        original_dateiname=original_dateiname,
        original_pdf_sha256=sha,
        original_pdf_bytes=pdf_bytes,
        status="parsing",
    )
    db.add(pl)
    db.flush()

    # Vision-Parsing — batch-weise für große PDFs
    images = pdf_to_page_images(pdf_bytes, dpi=200, max_pages=80)
    log.info("price_list_parsing", pages=len(images), price_list_id=pl.id)

    from app.core.config import settings as _settings

    batch_size = max(1, _settings.claude_pages_per_batch)
    eintraege: list[dict] = []
    seen_dna: set[str] = set()

    try:
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            log.info(
                "price_list_batch",
                batch=start // batch_size + 1,
                pages=f"{start + 1}-{start + len(batch)}",
            )
            parsed, model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
            for row in parsed.get("eintraege", []):
                # DNA-basiertes Dedup über Batch-Grenzen
                dna_key = "|".join(
                    str(row.get(k, "")) for k in (
                        "hersteller", "kategorie", "produktname", "abmessungen", "variante"
                    )
                )
                if dna_key in seen_dna:
                    continue
                seen_dna.add(dna_key)
                eintraege.append(row)
    except Exception as exc:
        log.error("price_list_parse_failed", error=str(exc), price_list_id=pl.id)
        pl.status = "error"
        db.commit()
        raise
    unsicher = 0
    for row in eintraege:
        preis = float(row.get("preis", 0.0) or 0.0)
        einheit = str(row.get("einheit", ""))
        preis_basis, basis_einheit = _normalize_to_base(
            preis,
            einheit,
            variante=str(row.get("variante", "")),
            abmessungen=str(row.get("abmessungen", "")),
        )
        konf = float(row.get("konfidenz", 1.0) or 1.0)
        if konf < 0.85:
            unsicher += 1
        entry = PriceEntry(
            price_list_id=pl.id,
            art_nr=str(row.get("art_nr", ""))[:100],
            hersteller=str(row.get("hersteller", ""))[:100],
            kategorie=str(row.get("kategorie", ""))[:100],
            produktname=str(row.get("produktname", ""))[:300],
            abmessungen=str(row.get("abmessungen", ""))[:200],
            variante=str(row.get("variante", ""))[:200],
            dna=build_dna(
                str(row.get("hersteller", "")),
                str(row.get("kategorie", "")),
                str(row.get("produktname", "")),
                str(row.get("abmessungen", "")),
                str(row.get("variante", "")),
            )[:500],
            preis=preis,
            einheit=einheit[:50],
            preis_pro_basis=preis_basis,
            basis_einheit=basis_einheit[:20],
            konfidenz=max(0.0, min(1.0, konf)),
        )
        db.add(entry)

    pl.eintraege_gesamt = len(eintraege)
    pl.eintraege_unsicher = unsicher
    pl.status = "review"
    db.commit()
    db.refresh(pl)
    log.info(
        "price_list_parsed",
        price_list_id=pl.id,
        model=model,
        total=len(eintraege),
        unsicher=unsicher,
    )
    return pl


def activate(db: Session, tenant_id: str, price_list_id: str) -> PriceList:
    """Markiert eine Liste als aktiv — deaktiviert andere aktive Listen desselben Händlers."""
    pl = (
        db.query(PriceList)
        .filter(PriceList.id == price_list_id, PriceList.tenant_id == tenant_id)
        .first()
    )
    if not pl:
        raise ValueError("Preisliste nicht gefunden")

    # Alle anderen aktiven Listen desselben Händlers deaktivieren
    db.query(PriceList).filter(
        PriceList.tenant_id == tenant_id,
        PriceList.haendler == pl.haendler,
        PriceList.id != pl.id,
        PriceList.aktiv.is_(True),
    ).update({"aktiv": False})

    pl.aktiv = True
    pl.status = "aktiv"
    db.commit()
    db.refresh(pl)
    return pl
