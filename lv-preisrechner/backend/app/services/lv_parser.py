"""Parser: LV-PDF → strukturierte Positionen."""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lv import LV
from app.models.position import Position
from app.services.claude_client import claude
from app.services.pdf_utils import compute_sha256, pdf_to_page_images, save_upload

log = structlog.get_logger()

SYSTEM_PROMPT = """Du bist Experte für Leistungsverzeichnisse (LV) im Trockenbau.

Du bekommst Bilder eines LV-PDFs vom Auftraggeber. Extrahiere ALLE Positionen strukturiert.

AUSGABEFORMAT (strikt):
{
  "projekt_name": "Verwaltungsgebäude Koblenz",
  "auftraggeber": "Löhr & Becker AG",
  "positionen": [
    {
      "reihenfolge": 1,
      "oz": "610.1",                        // Ordnungszahl aus LV (z.B. "01.01.001", "610.1")
      "titel": "Innenwände Trockenbau",     // Titel-/Untertitel-Überschrift falls vorhanden
      "kurztext": "Metallständerwand W112 ... GKB 12,5mm ...",
      "langtext": "",                       // ausführliche Beschreibung wenn vorhanden
      "menge": 42.5,                        // Zahl mit Punkt als Dezimaltrennzeichen
      "einheit": "m²",                       // "m²", "Stk", "lfm", "psch", "h"
      "erkanntes_system": "W112",           // siehe SYSTEM-REGELN unten
      "feuerwiderstand": "",                 // "F30" | "F60" | "F90" | "F120" | ""
      "plattentyp": "GKB",                   // "GKB" | "GKF" | "GKFi" | "GKBi" | "Diamant" | "Fireboard" | "Aquapanel" | ""
      "leit_fabrikat": "Knauf o.glw.",       // Leitfabrikat aus LV-Text: "Leitfabrikat: ..." / "Fabrikat: ..." - leer wenn nicht genannt
      "konfidenz": 0.92                      // 0.0-1.0
    }
  ]
}

SYSTEM-ERKENNUNGSREGELN (exakt DIESE Werte verwenden):
- "W112" = Standard-Trennwand, 1-lagig beplankt, meist GKB
- "W115" = Schallschutzwand, 2-lagig
- "W116" = Doppelständerwand
- "W118" = Brandschutzwand, 2-lagig GKF
- "W131" = Brandwand (eigenständig, schwerer Aufbau)
- "W135" = Installationswand, breitere UK
- "W135_Stahlblech" = Installationswand mit Stahlblecheinlage (F60 A+M, Einbruchhemmung)
- "W623" = Vorsatzschale freistehend
- "W625" = Vorsatzschale direkt befestigt
- "W625S" = Schachtwand einseitig beplankt (F30–F120)
- "W631" = Schachtwand zweiseitig
- "D112" = abgehängte GK-Decke, 1-lagig GKB
- "D113" = abgehängte GK-Decke, 2-lagig (Brand- oder Schallschutz)
- "OWA_MF" = OWA Mineralfaser-Rasterdecke (Bolero, Sinfonia, 625x625, 625x1250)
- "Aquapanel" = Nassraum-Wand mit Zementplatte
- "Verkleidung" = Abkofferung / Stahlträger-Bekleidung / Installations-Verkleidung (L/U-Form)
- "Deckenschuerze" = senkrechte Abschottung unter Decke
- "Tueraussparung" = Einbau Türzarge-Aussparung mit Sturzprofil
- "Revisionsklappe" = Revisionsklappe einbauen
- "Eckschiene" = ALU/verzinkte Kantenschiene (lfm)
- "Fugenversiegelung" = Acryl-Fuge (lfm)
- "Aussparung" = rechteckige Aussparung für Installation (Stk)
- "Installationsloch" = Rundloch für Sanitär (Stk)
- "Regiestunde" = Stundenlohn, einheit="h"
- "Zulage" = GKBi-Zulage, Eckausbildung, Arbeitshöhen-Zulage etc.

KEYWORDS für System-Erkennung:
- "MF-Rasterdecke", "Bolero", "Sinfonia", "Einlegesystem", "625x625", "625x1250" → OWA_MF
- "Mineralfaser-Raster" → OWA_MF (NICHT D112!)
- "Aquapanel", "Cement Board" → Aquapanel
- "Stahlblecheinlage", "A+M", "Einbruchhemmung" → W135_Stahlblech
- "Stundenlohn", "Regie", "Facharbeiter-Stunde" → Regiestunde (einheit="h")
- "Abkofferung", "Stahlträger-Verkleidung", "Fallrohr-Verkleidung" → Verkleidung
- "Deckenschürze" → Deckenschuerze
- "Türaussparung" → Tueraussparung
- "Installationsloch", "DN", "Durchbruch rund" → Installationsloch
- "Eckschiene", "Kantenschutz" → Eckschiene
- "Fugenversiegelung", "Acryl" → Fugenversiegelung

ANTWORTE AUSSCHLIESSLICH MIT JSON.
"""


def parse_and_store(
    *,
    db: Session,
    tenant_id: str,
    pdf_bytes: bytes,
    original_dateiname: str,
) -> LV:
    sha = compute_sha256(pdf_bytes)

    lv = LV(
        tenant_id=tenant_id,
        original_dateiname=original_dateiname,
        original_pdf_sha256=sha,
        original_pdf_bytes=pdf_bytes,
        status="extracting",
    )
    db.add(lv)
    db.flush()

    images = pdf_to_page_images(pdf_bytes, dpi=200, max_pages=80)
    log.info("lv_parsing", pages=len(images), lv_id=lv.id)

    from app.core.config import settings as _settings

    batch_size = max(1, _settings.claude_pages_per_batch)
    positionen: list[dict] = []
    projekt_name = ""
    auftraggeber = ""
    model = ""

    try:
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            log.info(
                "lv_batch",
                batch=start // batch_size + 1,
                pages=f"{start + 1}-{start + len(batch)}",
            )
            parsed, model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
            # Erstes Batch liefert Projekt-Metadaten
            if not projekt_name:
                projekt_name = str(parsed.get("projekt_name", ""))
            if not auftraggeber:
                auftraggeber = str(parsed.get("auftraggeber", ""))
            positionen.extend(parsed.get("positionen", []))
    except Exception as exc:
        log.error("lv_parse_failed", error=str(exc), lv_id=lv.id)
        lv.status = "error"
        db.commit()
        raise

    lv.projekt_name = projekt_name[:300]
    lv.auftraggeber = auftraggeber[:300]
    unsicher = 0
    for idx, row in enumerate(positionen):
        konf = float(row.get("konfidenz", 0.7) or 0.7)
        if konf < 0.85:
            unsicher += 1
        p = Position(
            lv_id=lv.id,
            reihenfolge=int(row.get("reihenfolge", idx + 1) or idx + 1),
            oz=str(row.get("oz", ""))[:50],
            titel=str(row.get("titel", ""))[:300],
            kurztext=str(row.get("kurztext", "")),
            langtext=str(row.get("langtext", "")),
            menge=float(row.get("menge", 0.0) or 0.0),
            einheit=str(row.get("einheit", ""))[:20],
            erkanntes_system=str(row.get("erkanntes_system", ""))[:50],
            feuerwiderstand=str(row.get("feuerwiderstand", ""))[:20],
            plattentyp=str(row.get("plattentyp", ""))[:50],
            leit_fabrikat=str(row.get("leit_fabrikat", ""))[:200],
            konfidenz=max(0.0, min(1.0, konf)),
        )
        db.add(p)

    lv.positionen_gesamt = len(positionen)
    lv.positionen_unsicher = unsicher
    lv.status = "review_needed"
    db.commit()
    db.refresh(lv)
    log.info(
        "lv_parsed", lv_id=lv.id, model=model, total=len(positionen), unsicher=unsicher
    )
    return lv
