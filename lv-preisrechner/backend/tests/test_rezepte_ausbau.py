"""Tests für die ausgebauten Rezepte + Alias-Resolver."""

from app.services.materialrezepte import REZEPTE, resolve_rezept


def test_owa_rezept_vorhanden():
    r = REZEPTE["OWA_MF"]
    assert r.system == "OWA_MF"
    assert r.zieleinheit == "m²"
    assert r.zeit_h_pro_einheit < 0.5  # Rasterdecken sind schnell montiert


def test_d113_rezept():
    r = REZEPTE["D113"]
    assert r.zeit_h_pro_einheit > REZEPTE["D112"].zeit_h_pro_einheit


def test_alias_rasterdecke_liefert_owa():
    assert resolve_rezept("RASTERDECKE", "", "") is REZEPTE["OWA_MF"]
    assert resolve_rezept("MF-Rasterdecke", "", "") is REZEPTE["OWA_MF"]
    assert resolve_rezept("OWA", "", "") is REZEPTE["OWA_MF"]


def test_alias_stundenlohn():
    assert resolve_rezept("Regiestunde", "", "") is REZEPTE["Regiestunde"]
    assert resolve_rezept("Stundenlohn", "", "") is REZEPTE["Regiestunde"]


def test_tueraussparung_alias():
    assert resolve_rezept("Türaussparung", "", "") is REZEPTE["Tueraussparung"]
    assert resolve_rezept("Tueraussparung", "", "") is REZEPTE["Tueraussparung"]


def test_abkofferung_alias_liefert_verkleidung():
    assert resolve_rezept("Abkofferung", "", "") is REZEPTE["Verkleidung"]


def test_aquapanel_alias():
    r = resolve_rezept("Aquapanel-Wand", "", "")
    assert r is REZEPTE["Aquapanel"]


def test_d11x_prefix_heuristik():
    r = resolve_rezept("D114", "", "")
    assert r is REZEPTE["D112"]


def test_d13_prefix_heuristik():
    r = resolve_rezept("D131", "", "")
    assert r is REZEPTE["D113"]


def test_w13_prefix_heuristik():
    r = resolve_rezept("W132", "F90", "")
    assert r is REZEPTE["W131"]


def test_w118_bei_feuerwiderstand_und_w11x():
    assert resolve_rezept("W114", "F90", "GKF") is REZEPTE["W118"]
    assert resolve_rezept("W114", "", "") is REZEPTE["W112"]
