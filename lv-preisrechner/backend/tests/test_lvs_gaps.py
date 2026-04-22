"""B+4.3.0c Golden-Tests fuer den Catalog-Gaps-Endpoint.

GET /api/v1/lvs/{lv_id}/gaps

Bis zu diesem Commit existiert der Endpoint noch nicht — die Tests,
die erwartete Antwort-Struktur pruefen, liefern 404 und sollen damit
**rot** sein. Guards, die ein 404 erwarten (unbekanntes LV, fremder
Tenant) sind zufaellig **gruen**, bleiben aber nach dem Fix aus
inhaltlichem Grund gruen.

Test-Strategie:
- Statt kalkuliere_lv() zu fahren, werden Positionen mit einem
  hand-konstruierten materialien-JSON seediert. So sind price_source
  und match_confidence deterministisch, unabhaengig von Matcher-
  Details oder aktiven Preislisten.
- Jede Material-Zeile im JSON entspricht dem in B+4.2 definierten
  Schema (dna, menge, einheit, price_source, match_confidence,
  source_description, needs_review, …).
- Fixtures setzen unterschiedliche Szenarien zusammen (nur missing,
  nur estimated, gemischt, ohne Gaps).

Docstrings folgen dem 4-Abschnitt-Muster (Zweck, Initialstatus,
Nach-Fix-Status, Warnsatz).
"""

from __future__ import annotations

from typing import Any

from app.models.lv import LV
from app.models.position import Position
from app.models.tenant import Tenant
from app.models.user import User


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _register_and_login(c, email: str, firma: str = "TestBetrieb") -> str:
    resp = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "Test",
            "nachname": "User",
            "firma": firma,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.core import database
    return database.SessionLocal()


def _tenant_of_token(c, token: str) -> str:
    me = c.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200
    return me.json()["tenant_id"]


def _mat(
    dna: str,
    *,
    menge: float = 1.0,
    einheit: str = "m²",
    price_source: str,
    match_confidence: float | None = None,
    source_description: str = "",
    needs_review: bool | None = None,
    preis_einheit: float = 0.0,
) -> dict[str, Any]:
    """Kompakter Builder fuer ein Material-JSON-Item.

    needs_review wird abgeleitet falls nicht uebergeben:
    - supplier_price + confidence >= 0.85 -> False
    - sonst -> True
    """
    if needs_review is None:
        if price_source == "supplier_price" and (
            match_confidence is not None and match_confidence >= 0.85
        ):
            needs_review = False
        else:
            needs_review = True
    return {
        "dna": dna,
        "menge": menge,
        "einheit": einheit,
        "preis_einheit": preis_einheit,
        "gp": round(menge * preis_einheit, 2),
        "price_source": price_source,
        "source_description": source_description,
        "applied_discount_percent": None,
        "needs_review": needs_review,
        "match_confidence": match_confidence,
    }


def _seed_lv_with_positions(
    db,
    tenant_id: str,
    positions_spec: list[dict[str, Any]],
    *,
    filename: str = "gaps-test.pdf",
) -> str:
    """Erzeugt ein LV mit Positionen laut Spezifikation.

    positions_spec: Liste dict mit Keys: oz (str), kurztext (str),
    erkanntes_system (str), materialien (list[dict]).
    Rueckgabe: lv_id.
    """
    lv = LV(
        tenant_id=tenant_id,
        original_dateiname=filename,
        status="calculated",
    )
    db.add(lv)
    db.flush()
    for i, ps in enumerate(positions_spec):
        any_review = any(m.get("needs_review") for m in ps.get("materialien", []))
        p = Position(
            lv_id=lv.id,
            reihenfolge=i,
            oz=ps["oz"],
            kurztext=ps.get("kurztext", ""),
            menge=ps.get("menge", 1.0),
            einheit=ps.get("einheit", "m²"),
            erkanntes_system=ps.get("erkanntes_system", ""),
            feuerwiderstand=ps.get("feuerwiderstand", "F0"),
            plattentyp=ps.get("plattentyp", "GKB"),
            materialien=ps.get("materialien", []),
            needs_price_review=any_review,
        )
        db.add(p)
    db.commit()
    return lv.id


def _setup_basic(client, email="gaps@example.com", firma="GapsBetrieb") -> str:
    """Login + return token. Kein LV."""
    return _register_and_login(client, email, firma=firma)


# --------------------------------------------------------------------------- #
# Test 1 — Happy Path mit gemischten Severities
# --------------------------------------------------------------------------- #
def test_gaps_happy_path_mixed_severities(client):
    """Response enthaelt missing + estimated, Counter stimmen.

    Zweck: Grundfunktion pruefen — Endpoint liefert korrekt strukturierte
    Gap-Eintraege mit passender severity und Counter-Invariante.

    Initialstatus: ROT, Endpoint existiert nicht (404).

    Nach Fix: GRUEN. gaps_count == 2 (1 missing + 1 estimated),
    das supplier_price-Material erscheint nicht.

    Warnsatz: bricht dieser Test nach dem Fix, ist entweder die
    Severity-Klassifikation falsch oder ein matchendes Material wurde
    faelschlicherweise als Gap eingestuft.
    """
    token = _setup_basic(client, email="happy@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [
                {
                    "oz": "1.1",
                    "kurztext": "Metallstaenderwand",
                    "erkanntes_system": "W112",
                    "materialien": [
                        _mat(
                            "Knauf|Gipskarton|GKB|12.5|",
                            price_source="supplier_price",
                            match_confidence=0.92,
                            source_description="Kemmler-Listenpreis",
                        ),
                        _mat(
                            "|Daemmung||40mm|",
                            price_source="estimated",
                            match_confidence=0.5,
                            source_description="Ø aus Kategorie Daemmung",
                        ),
                        _mat(
                            "Knauf|Profile|CW|75|",
                            price_source="not_found",
                            match_confidence=None,
                            source_description="Kein Match",
                        ),
                    ],
                },
            ],
        )
    finally:
        db.close()

    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["lv_id"] == lv_id
    assert body["total_positions"] == 1
    assert body["total_materials"] == 3
    assert body["gaps_count"] == 2
    assert body["missing_count"] == 1
    assert body["estimated_count"] == 1
    assert body["low_confidence_count"] == 0
    assert len(body["gaps"]) == 2

    severities = {g["severity"] for g in body["gaps"]}
    assert severities == {"missing", "estimated"}
    # Counter-Invariante
    assert body["gaps_count"] == (
        body["missing_count"] + body["estimated_count"]
        + body["low_confidence_count"]
    )


# --------------------------------------------------------------------------- #
# Test 2 — Deterministische Severity-Sortierung
# --------------------------------------------------------------------------- #
def test_gaps_sorted_missing_before_estimated(client):
    """Severity-Reihenfolge: missing vor estimated.

    Zweck: sicherstellen, dass die gaps-Liste in der im Baseline-Doc
    festgelegten Ordnung geliefert wird (missing > low_confidence >
    estimated), auch wenn im zugrundeliegenden materialien-JSON die
    Reihenfolge anders ist.

    Initialstatus: ROT (404).

    Nach Fix: GRUEN. Erstes Element ist severity=missing, letztes ist
    severity=estimated.

    Warnsatz: bricht dieser Test, ist das Frontend nicht mehr in der
    Lage, Gaps per Default-Sortierung priorisiert anzuzeigen.
    """
    token = _setup_basic(client, email="sort@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [
                {
                    "oz": "1.1",
                    "erkanntes_system": "W112",
                    "materialien": [
                        _mat("a|b|A|x|", price_source="estimated", match_confidence=0.5),
                        _mat("a|b|B|y|", price_source="not_found"),
                    ],
                },
            ],
        )
    finally:
        db.close()

    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r.status_code == 200, r.text
    gaps = r.json()["gaps"]
    assert len(gaps) == 2
    assert gaps[0]["severity"] == "missing"
    assert gaps[-1]["severity"] == "estimated"


# --------------------------------------------------------------------------- #
# Test 3 — LV ohne Gaps (Guard)
# --------------------------------------------------------------------------- #
def test_gaps_empty_when_all_materials_match(client):
    """LV ohne Problem-Materialien -> leere gaps-Liste.

    Zweck: LVs mit ausschliesslich sauberen supplier_price-Matches
    produzieren keinen Rauschen im Report.

    Initialstatus: im heutigen Stand wuerde der Call ein 404 liefern,
    weil der Endpoint fehlt. Dieser Test ist damit aktuell **rot**
    (der Counter-Check gegen 200 schlaegt fehl) — NICHT zufaellig
    gruen. Siehe Anmerkung unten.

    Nach Fix: GRUEN aus inhaltlichem Grund — gaps-Liste ist leer,
    alle Counter sind 0.

    Warnsatz: bricht dieser Test nach dem Fix, wird ein matchendes
    Material faelschlicherweise als Gap eingestuft.
    """
    token = _setup_basic(client, email="empty@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [
                {
                    "oz": "1.1",
                    "erkanntes_system": "W112",
                    "materialien": [
                        _mat("x|y|z|1|",
                             price_source="supplier_price",
                             match_confidence=0.95),
                        _mat("x|y|z|2|",
                             price_source="supplier_price",
                             match_confidence=0.91),
                    ],
                },
            ],
        )
    finally:
        db.close()

    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gaps"] == []
    assert body["gaps_count"] == 0
    assert body["missing_count"] == 0
    assert body["estimated_count"] == 0
    assert body["low_confidence_count"] == 0


# --------------------------------------------------------------------------- #
# Test 4 — severity=missing
# --------------------------------------------------------------------------- #
def test_gaps_missing_semantics(client):
    """price_source=not_found -> severity=missing, match_confidence=None.

    Zweck: Kerngrundfall abdecken. Material ohne Match wird korrekt
    gekennzeichnet, match_confidence wird als None transportiert
    (nicht 0.0).

    Initialstatus: ROT (404).

    Nach Fix: GRUEN.

    Warnsatz: bricht dieser Test, ist entweder das match_confidence-
    Mapping falsch (0.0 statt None) oder die severity-Klassifikation
    verwechselt missing mit estimated.
    """
    token = _setup_basic(client, email="missing@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [{
                "oz": "2.1",
                "erkanntes_system": "W628A",
                "materialien": [
                    _mat("Knauf|Gipskarton|Fireboard|12.5|",
                         price_source="not_found",
                         source_description="Kein Katalog-Eintrag"),
                ],
            }],
        )
    finally:
        db.close()

    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r.status_code == 200, r.text
    gaps = r.json()["gaps"]
    assert len(gaps) == 1
    g = gaps[0]
    assert g["severity"] == "missing"
    assert g["price_source"] == "not_found"
    assert g["match_confidence"] is None
    # material_name aus DNA-Parse
    assert "Fireboard" in g["material_name"]


# --------------------------------------------------------------------------- #
# Test 5 — severity=estimated
# --------------------------------------------------------------------------- #
def test_gaps_estimated_semantics(client):
    """price_source=estimated -> severity=estimated, match_confidence gesetzt.

    Zweck: Kategorie-Mittelwert-Match wird korrekt als Gap
    klassifiziert, match_confidence wird durchgereicht.

    Initialstatus: ROT (404).

    Nach Fix: GRUEN.

    Warnsatz: bricht dieser Test, ist der estimated-Pfad nicht mehr
    ordentlich abgebildet — das Backend liefert Gaps unvollstaendig.
    """
    token = _setup_basic(client, email="estimated@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [{
                "oz": "2.2",
                "erkanntes_system": "W112",
                "materialien": [
                    _mat("|Daemmung||40mm|",
                         price_source="estimated",
                         match_confidence=0.5,
                         source_description="Ø aus Kategorie Daemmung (17 Eintraege)"),
                ],
            }],
        )
    finally:
        db.close()

    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r.status_code == 200, r.text
    gaps = r.json()["gaps"]
    assert len(gaps) == 1
    g = gaps[0]
    assert g["severity"] == "estimated"
    assert g["price_source"] == "estimated"
    assert g["match_confidence"] == 0.5


# --------------------------------------------------------------------------- #
# Test 6 — low_confidence mit include_low_confidence=true
# --------------------------------------------------------------------------- #
def test_gaps_low_confidence_opt_in_threshold(client):
    """?include_low_confidence=true: supplier_price <0.5 erscheint, >=0.5 nicht.

    Zweck: Schwellen-Verifikation fuer den Opt-in-Modus. Die Schwelle
    0.5 trennt harte low_confidence-Gaps von regulaeren supplier_price-
    Matches.

    Initialstatus: ROT (404).

    Nach Fix: GRUEN. Nur der 0.45-Eintrag erscheint; der 0.60-Eintrag
    wird nicht als Gap gezaehlt.

    Warnsatz: bricht dieser Test, ist entweder die Schwelle falsch
    konfiguriert oder das Opt-in greift ueber den vorgesehenen Scope
    hinaus.
    """
    token = _setup_basic(client, email="lowopt@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [{
                "oz": "3.1",
                "erkanntes_system": "W133",
                "materialien": [
                    _mat("a|b|unter|x|",
                         price_source="supplier_price",
                         match_confidence=0.45,
                         source_description="wackeliger Match"),
                    _mat("a|b|ueber|y|",
                         price_source="supplier_price",
                         match_confidence=0.60,
                         source_description="eher solide"),
                ],
            }],
        )
    finally:
        db.close()

    r = client.get(
        f"/api/v1/lvs/{lv_id}/gaps?include_low_confidence=true",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gaps_count"] == 1
    assert body["low_confidence_count"] == 1
    assert body["missing_count"] == 0
    assert body["estimated_count"] == 0
    g = body["gaps"][0]
    assert g["severity"] == "low_confidence"
    assert g["match_confidence"] == 0.45


# --------------------------------------------------------------------------- #
# Test 7 — Default ohne Parameter: low_confidence NICHT dabei
# --------------------------------------------------------------------------- #
def test_gaps_low_confidence_default_off(client):
    """Ohne include_low_confidence erscheinen keine low_confidence-Gaps.

    Zweck: Opt-in-Verifikation. Der Default-Modus listet nur missing
    und estimated. supplier_price-Matches mit niedriger Confidence
    bleiben unsichtbar.

    Initialstatus: ROT (404).

    Nach Fix: GRUEN. gaps-Liste ist leer.

    Warnsatz: bricht dieser Test, geraten low_confidence-Eintraege in
    die Default-Sicht und verwaessern den "echte Probleme"-Fokus des
    Tabs.
    """
    token = _setup_basic(client, email="lowdef@example.com")
    tenant_id = _tenant_of_token(client, token)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_id,
            [{
                "oz": "3.1",
                "erkanntes_system": "W133",
                "materialien": [
                    _mat("a|b|unter|x|",
                         price_source="supplier_price",
                         match_confidence=0.45),
                    _mat("a|b|ueber|y|",
                         price_source="supplier_price",
                         match_confidence=0.60),
                ],
            }],
        )
    finally:
        db.close()

    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gaps_count"] == 0
    assert body["low_confidence_count"] == 0
    assert body["gaps"] == []


# --------------------------------------------------------------------------- #
# Test 8 — 404 bei unbekanntem LV (Guard)
# --------------------------------------------------------------------------- #
def test_gaps_unknown_lv_returns_404(client):
    """Unbekannte lv_id -> 404.

    Zweck: konsistenter Umgang mit nicht-existenten Ressourcen.

    Initialstatus: GRUEN (Endpoint fehlt, FastAPI liefert 404 aus dem
    Router). Test ist zufaellig gruen.

    Nach Fix: GRUEN aus inhaltlichem Grund — der Endpoint prueft
    selbst gegen die DB und gibt 404 bei Miss zurueck.

    Warnsatz: bricht dieser Test, leakt der Endpoint irgendwie
    Informationen zu nicht-existenten LVs (z. B. 500 oder 200 mit
    leerem Body).
    """
    token = _setup_basic(client, email="unknown@example.com")
    r = client.get(
        "/api/v1/lvs/does-not-exist-12345678/gaps",
        headers=_auth(token),
    )
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Test 9 — 401 ohne Auth
# --------------------------------------------------------------------------- #
def test_gaps_unauthenticated_returns_401(client):
    """Fehlendes Token -> 401.

    Zweck: Auth-Pflicht bestaetigen.

    Initialstatus: ROT. Ohne Auth-Header trifft FastAPI den Security-
    Handler und liefert 401. Das ist das erwartete Verhalten schon
    heute, unabhaengig vom Endpoint.

    Nach Fix: GRUEN aus inhaltlichem Grund.

    Warnsatz: bricht dieser Test, wurde das Auth-Depend versehentlich
    entfernt oder der Endpoint haengt an einem anderen Router.
    """
    r = client.get("/api/v1/lvs/any-id/gaps")
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# Test 10 — 404 bei LV in fremdem Tenant (Guard)
# --------------------------------------------------------------------------- #
def test_gaps_foreign_tenant_returns_404(client):
    """Fremdes Tenant-LV -> 404 (keine Info-Leakage als 403).

    Zweck: Tenant-Isolation pruefen. Zugriff auf LV eines anderen
    Tenants wird konsistent wie 'nicht existent' behandelt.

    Initialstatus: im heutigen Stand 404, weil der Endpoint gar nicht
    existiert. Test ist zufaellig gruen — der inhaltliche Tenant-Check
    wird nicht geprueft. Siehe Nach-Fix-Kommentar.

    Nach Fix: GRUEN aus inhaltlichem Grund — der Endpoint prueft
    lv.tenant_id gegen user.tenant_id und liefert 404 bei Mismatch.

    Warnsatz: bricht dieser Test nach dem Fix, hat sich die Tenant-
    Isolation veraendert (z. B. 403 statt 404 oder 200 mit fremden
    Daten) — das waere ein Sicherheits-Issue.
    """
    # Tenant A erstellt LV
    token_a = _register_and_login(client, "a-gaps@example.com", firma="A")
    tenant_a = _tenant_of_token(client, token_a)
    db = _db()
    try:
        lv_id = _seed_lv_with_positions(
            db, tenant_a,
            [{
                "oz": "1.1",
                "erkanntes_system": "W112",
                "materialien": [_mat("a|b|c|1|", price_source="not_found")],
            }],
        )
    finally:
        db.close()

    # Tenant B versucht Zugriff
    token_b = _register_and_login(client, "b-gaps@example.com", firma="B")
    r = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token_b))
    assert r.status_code == 404
