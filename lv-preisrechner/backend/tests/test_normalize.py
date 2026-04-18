"""Tests: Einheit-Normalisierung (Gebinde-Preise, Paketpreise)."""

from app.services.price_list_parser import _normalize_to_base


def test_m2_unveraendert():
    p, e = _normalize_to_base(3.00, "€/m²")
    assert (p, e) == (3.00, "m²")


def test_paket_500_stk_wird_zu_pro_stk():
    p, e = _normalize_to_base(21.07, "€/Paket (500 Stk)")
    assert e == "Stk"
    assert abs(p - 21.07 / 500) < 0.0001


def test_buendel_bl_3m_wird_zu_lfm():
    # "95.70 €/Bd., 16 St./Bd., BL=3000mm" → 16*3m = 48lfm → 95.70/48 ≈ 1.99 €/lfm
    p, e = _normalize_to_base(
        95.70,
        "€/Bd.",
        variante="BL=3000mm, 16 St./Bd.",
    )
    assert e == "lfm"
    assert abs(p - 95.70 / 48) < 0.01


def test_buendel_bl_in_abmessung():
    p, e = _normalize_to_base(
        95.70,
        "€/Bd.",
        abmessungen="48x24mm",
        variante="16 St./Bd., BL=3m",
    )
    assert e == "lfm"
    assert abs(p - 95.70 / 48) < 0.01


def test_kg_erkannt():
    p, e = _normalize_to_base(1.36, "€/kg")
    assert (p, e) == (1.36, "kg")


def test_lfm_erkannt():
    p, e = _normalize_to_base(1.13, "€/lfm")
    assert (p, e) == (1.13, "lfm")


def test_stk_einfach():
    p, e = _normalize_to_base(43.77, "€/Stk")
    assert (p, e) == (43.77, "Stk")
