"""Tests fuer den Knauf-Rezept-Loader (B+4.13 Iter 5b 2026-04-29)."""
from __future__ import annotations

from app.services.knauf_recipe_loader import (
    KnaufSystemSpec,
    get_recipe_provenance,
    load_all_knauf_systems,
)


def test_loader_findet_alle_yaml_systeme():
    """Mindestens W112 und W628B muessen geladen werden — das sind die
    kalibrierten Hauptsysteme."""
    specs = load_all_knauf_systems()
    assert "W112" in specs
    assert "W628B" in specs
    # Multi-variant-Datei wird in einzelne Specs aufgeteilt
    assert "W625" in specs


def test_w112_spec_hat_quellenangabe():
    specs = load_all_knauf_systems()
    s = specs["W112"]
    assert isinstance(s, KnaufSystemSpec)
    assert "W11.de" in s.quelle_dokument
    assert "2024" in s.quelle_dokument
    # YAML laedt das Datum als datetime.date, also string-Vergleich ueber str()
    assert str(s.quelle_abgerufen) == "2026-04-29"
    assert 67 in s.quelle_seiten  # Befestigungs-Seite


def test_w628b_befestigung_verified():
    specs = load_all_knauf_systems()
    s = specs["W628B"]
    assert s.has_befestigung_verified
    assert s.has_unterkonstruktion_verified


def test_get_recipe_provenance_format():
    p = get_recipe_provenance("W112")
    assert p is not None
    assert "W11.de" in p
    assert "67" in p  # Seitennummer enthalten
    assert "2026-04-29" in p


def test_unbekanntes_system_liefert_none():
    assert get_recipe_provenance("W999") is None
