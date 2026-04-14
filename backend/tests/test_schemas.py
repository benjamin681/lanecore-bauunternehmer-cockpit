"""Schema validation tests."""

import pytest
from pydantic import ValidationError

from app.schemas.projekt import ProjektCreate
from app.schemas.bauplan import RaumSchema, WandSchema, DeckeSchema


def test_projekt_create_valid():
    p = ProjektCreate(name="Himmelweiler III", auftraggeber="Max GmbH")
    assert p.name == "Himmelweiler III"


def test_projekt_create_name_too_short():
    with pytest.raises(ValidationError):
        ProjektCreate(name="X")


def test_raum_schema():
    r = RaumSchema(bezeichnung="Büro 1.01", flaeche_m2=24.5, hoehe_m=2.8)
    assert r.flaeche_m2 == 24.5


def test_wand_schema():
    w = WandSchema(id="W1", typ="W112", laenge_m=8.4, hoehe_m=2.8)
    assert w.typ == "W112"
    assert w.unsicher is False


def test_decke_schema():
    d = DeckeSchema(
        raum="WC Herren",
        typ="Aquapanel-Decke",
        system="HKD",
        flaeche_m2=6.8,
        abhaengehoehe_m=0.25,
    )
    assert d.system == "HKD"
    assert d.entfaellt is False


def test_decke_entfaellt():
    d = DeckeSchema(raum="Flur", typ="GKb-Abhangdecke", flaeche_m2=12.0, entfaellt=True)
    assert d.entfaellt is True
