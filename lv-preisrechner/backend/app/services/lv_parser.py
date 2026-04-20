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

Wände Knauf W11x (Metallständerwände, beidseitig beplankt):
- "W112" = Standard-Trennwand, 1-lagig beplankt, meist GKB (F0 ODER F30 abhängig von Plattentyp)
- "W115" = Schallschutzwand, 2-lagig
- "W116" = Doppelständerwand (Installationswand)
- "W118" = Brandschutzwand 2-lagig GKF (F90)
- "W131" = einschalige Brandwand (eigenständig, schwerer Aufbau, F90/F120)
- "W133" = zweischalige Brandwand (zwei getrennte Profilreihen, höhere Anforderung)
- "W135" = Installationswand, breitere UK
- "W135_Stahlblech" = Installationswand mit Stahlblecheinlage (F60 A+M, Einbruchhemmung)

Vorsatzschalen Knauf W62x (einseitig, vor Bestandswand):
- "W623" = Vorsatzschale freistehend (CW/UW-Profile)
- "W625" = Vorsatzschale direkt befestigt (Direktabhänger CD60/27)

Schachtwände Knauf W62x/W63x (Schacht-Abschottung, einseitig oder zweiseitig):
- "W625S" = Schachtwand einseitig beplankt mit Fireboard (F30–F120)
- "W628" = Einschalen-Schachtwand einseitig beplankt (Standard Knauf, meist GKF 2x12,5, F30–F90). Auch "Einschalen-Schachtwand".
- "W628A" = wie W628, Variante für erhöhte Wandhöhe (Knauf "W628A plus" o.ä., bis ca. 8.9m Höhe)
- "W630" = Schachtwand einseitig in "plus"-Variante (verstärkte Konstruktion, F90-fähig). Wenn LV "W630 plus" oder "W 630" erwähnt.
- "W631" = Schachtwand zweiseitig beplankt (beide Seiten vom Schacht aus)

Decken:
- "D112" = abgehängte GK-Decke, 1-lagig GKB
- "D113" = abgehängte GK-Decke, 2-lagig (Brand- oder Schallschutz)
- "OWA_MF" = OWA Mineralfaser-Rasterdecke (Bolero, Sinfonia, OWATECTA, 625x625, 625x1250)
- "Streckmetalldecke" = Streckmetall-Rasterdecke (Lindner LMD, rahmenlos, offene Fuge)
- "Deckensegel" = Akustik-Deckensegel freihängend (Strähle System 7300 o.glw.)
- "Deckensprung" = senkrechter Höhenversatz in Rasterdecke oder Abhangdecke

Akustik:
- "Wandabsorber" = Tiefenabsorber an der Wand (DUR SONIC Quad o.glw., Pulverbeschichtet)

Nassraum:
- "Aquapanel" = Nassraum-Wand/Decke mit Zementplatte

Sonderverkleidungen:
- "Verkleidung" = GK-Verkleidung (Stahlträger/Stahltreppe/Fallrohr-Abkofferung L/U-Form)
- "Deckenschuerze" = senkrechte GK-Abschottung unter Bestandsdecke (abgehängter Streifen)
- "Deckenschott" = Brandschutz-Deckenschott (F90 Abschottung senkrecht vom Deckenanschluss)

Zubehör/Nebenleistungen:
- "Tueraussparung" = Einbau Türzarge-Aussparung mit Sturzprofil in GK-Wand
- "Revisionsklappe" = Revisionsklappe einbauen (30x30 bis 60x60)
- "Eckschiene" = ALU/verzinkte Kantenschiene (lfm)
- "Fugenversiegelung" = Acryl-/Brandschutz-Fuge (lfm)
- "Aussparung" = rechteckige Aussparung für Installation (Stk)
- "Installationsloch" = Rundloch für Sanitär (Stk)
- "Wandanschluss" = Randfries/Wandanschluss bei Rasterdecke oder GK-Decke
- "Verstaerkungsprofil" = Z-Profil, QR-Profil, UA-Verstärkung horizontal (lfm)
- "Kabeldurchfuehrung_F90" = Einzelkabeldurchführung F90 in Brandschutzdecke
- "Aufdopplung_geklebt" = geklebte GK-Aufdopplung (Ansetzbinder, z.B. h=0.25m)

Regie:
- "Regiestunde" = Stundenlohnarbeit, einheit="h"
- "Zulage" = GKBi-Zulage, Q3-Zulage, Arbeitshöhen-Zulage etc.

KEYWORDS für System-Erkennung (Prioritäts-Reihenfolge!):

Schachtwände (WICHTIG: vor Vorsatzschale prüfen):
- "W628", "W 628", "W628A", "Einschalen-Schachtwand" → W628 oder W628A (bei "A" oder "plus" + erhöhte Höhe)
- "W630", "W 630", "W630 plus", "Schachtwand plus" → W630
- "W631", "Schachtwand zweiseitig" → W631
- "Schachtwand" (ohne Nummer) + einseitig → W625S als Default

Brandschutz:
- "W131", "einschalige Brandwand" → W131
- "W133", "zweischalige Brandwand" → W133
- "Stahlblecheinlage", "A+M", "Einbruchhemmung" → W135_Stahlblech

Decken:
- "MF-Rasterdecke", "Bolero", "Sinfonia", "OWATECTA", "Einlegesystem", "625x625", "625x1250" → OWA_MF
- "Mineralfaser-Raster" → OWA_MF (NICHT D112!)
- "LMD", "Streckmetall", "rahmenlos" → Streckmetalldecke
- "Deckensegel", "Akustiksegel", "Strähle", "System 7300" → Deckensegel
- "Deckensprung" → Deckensprung

Akustik:
- "Wandabsorber", "Tiefenabsorber", "DUR SONIC", "Akustikabsorber Wand" → Wandabsorber

Nassraum:
- "Aquapanel", "Cement Board", "Powerpanel" → Aquapanel

Sonstiges:
- "Stundenlohn", "Regie", "Facharbeiter-Stunde", "Helferstunde" → Regiestunde (einheit="h")
- "Abkofferung", "Stahlträger-Verkleidung", "Fallrohr-Verkleidung", "GK-Verkleidung unter Treppe" → Verkleidung
- "Deckenschürze" → Deckenschuerze
- "Deckenschott", "Brandschutzabschottung senkrecht" → Deckenschott
- "Türaussparung", "Fenster/Türaussparung" → Tueraussparung
- "Installationsloch", "DN", "Durchbruch rund" → Installationsloch
- "Eckschiene", "Kantenschutz" → Eckschiene
- "Fugenversiegelung", "Acryl", "Dehnungsfuge", "Bewegungsfuge" → Fugenversiegelung
- "Wandanschluss", "Randfries" → Wandanschluss
- "Z-Profil", "QR-Profil", "Verstärkungsprofil", "UA-Verstärkung horizontal" → Verstaerkungsprofil
- "Einzelkabeldurchführung F90", "Kabelschott F90" → Kabeldurchfuehrung_F90
- "Aufdopplung", "GK-Platten geklebt" → Aufdopplung_geklebt

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
