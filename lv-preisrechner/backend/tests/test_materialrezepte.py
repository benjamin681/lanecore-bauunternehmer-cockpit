"""Tests für Rezept-Auflösung."""

from app.services.materialrezepte import REZEPTE, resolve_rezept


def test_w112_rezept_direkt():
    r = resolve_rezept("W112", "", "GKB")
    assert r is not None
    assert r.system == "W112"


def test_w118_brandschutz():
    r = resolve_rezept("W118", "F90", "GKF")
    assert r is not None
    assert r.system == "W118"


def test_w11x_unbekannt_mit_feuerwiderstand_gibt_w118():
    r = resolve_rezept("W114", "F90", "GKF")
    assert r is not None
    assert r.system == "W118"


def test_w11x_unbekannt_ohne_feuerwiderstand_gibt_w112():
    r = resolve_rezept("W114", "", "GKB")
    assert r is not None
    assert r.system == "W112"


def test_unbekanntes_system_gibt_none():
    r = resolve_rezept("ZZZ999", "", "")
    assert r is None


def test_alle_rezepte_haben_materialien_oder_zeit():
    for sys_name, rez in REZEPTE.items():
        # Ausnahme: "Zulage" hat bewusst keine Materialien
        assert rez.zeit_h_pro_einheit > 0, f"{sys_name}: keine Zeit definiert"
