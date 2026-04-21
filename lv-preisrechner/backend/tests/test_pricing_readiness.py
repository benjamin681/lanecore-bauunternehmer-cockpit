"""Tests fuer /api/v1/pricing/readiness + use_new_pricing-Toggle
(B+4.3.1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.pricing import (
    PricelistStatus,
    SupplierPriceList,
    TenantPriceOverride,
)


def _register_and_login(client, email="a@example.com", firma="Test GmbH"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test1234", "firma": firma},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    tenant_id = resp.json()["user_id"]  # dummy, echter tenant holen wir via /me
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _tenant_id(client, token):
    r = client.get("/api/v1/auth/me", headers=_auth(token))
    return r.json()["tenant_id"]


# ---------------------------------------------------------------------------
# /pricing/readiness — drei Basis-Faelle
# ---------------------------------------------------------------------------
def test_readiness_leer_ist_not_ready(client):
    token = _register_and_login(client, email="leer@example.com")
    r = client.get("/api/v1/pricing/readiness", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "has_active_pricelist": False,
        "has_overrides": False,
        "ready_for_new_pricing": False,
    }


def test_readiness_mit_aktiver_pricelist_ready(client):
    from app.core import database
    token = _register_and_login(client, email="pl@example.com")
    tenant_id = _tenant_id(client, token)
    s = database.SessionLocal()
    try:
        # User holen (fuer uploaded_by_user_id)
        from app.models.user import User
        u = s.query(User).filter(User.tenant_id == tenant_id).first()
        assert u is not None
        pl = SupplierPriceList(
            tenant_id=tenant_id,
            supplier_name="Kemmler",
            list_name="Test",
            valid_from=date(2026, 1, 1),
            source_file_path="/tmp/x.pdf",
            source_file_hash="h1",
            status=PricelistStatus.APPROVED.value,
            is_active=True,
            uploaded_by_user_id=u.id,
        )
        s.add(pl)
        s.commit()
    finally:
        s.close()
    r = client.get("/api/v1/pricing/readiness", headers=_auth(token))
    body = r.json()
    assert body["has_active_pricelist"] is True
    assert body["has_overrides"] is False
    assert body["ready_for_new_pricing"] is True


def test_readiness_nur_override_ready(client):
    from app.core import database
    token = _register_and_login(client, email="ov@example.com")
    tenant_id = _tenant_id(client, token)
    s = database.SessionLocal()
    try:
        from app.models.user import User
        u = s.query(User).filter(User.tenant_id == tenant_id).first()
        o = TenantPriceOverride(
            tenant_id=tenant_id,
            article_number="ART-001",
            override_price=Decimal("1.23"),
            unit="m²",
            valid_from=date(2026, 1, 1),
            created_by_user_id=u.id,
        )
        s.add(o)
        s.commit()
    finally:
        s.close()
    r = client.get("/api/v1/pricing/readiness", headers=_auth(token))
    body = r.json()
    assert body["has_active_pricelist"] is False
    assert body["has_overrides"] is True
    assert body["ready_for_new_pricing"] is True


def test_readiness_beide_true(client):
    from app.core import database
    token = _register_and_login(client, email="beide@example.com")
    tenant_id = _tenant_id(client, token)
    s = database.SessionLocal()
    try:
        from app.models.user import User
        u = s.query(User).filter(User.tenant_id == tenant_id).first()
        pl = SupplierPriceList(
            tenant_id=tenant_id,
            supplier_name="K",
            list_name="L",
            valid_from=date(2026, 1, 1),
            source_file_path="/tmp/a.pdf",
            source_file_hash="h2",
            status=PricelistStatus.APPROVED.value,
            is_active=True,
            uploaded_by_user_id=u.id,
        )
        s.add(pl)
        s.add(TenantPriceOverride(
            tenant_id=tenant_id,
            article_number="ART-002",
            override_price=Decimal("1"),
            unit="m²",
            valid_from=date(2026, 1, 1),
            created_by_user_id=u.id,
        ))
        s.commit()
    finally:
        s.close()
    r = client.get("/api/v1/pricing/readiness", headers=_auth(token))
    body = r.json()
    assert body["has_active_pricelist"] is True
    assert body["has_overrides"] is True
    assert body["ready_for_new_pricing"] is True


# ---------------------------------------------------------------------------
# PATCH /auth/me/tenant — Flag-Aktivierung
# ---------------------------------------------------------------------------
def test_me_exposes_use_new_pricing_default_false(client):
    token = _register_and_login(client, email="me@example.com")
    r = client.get("/api/v1/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["use_new_pricing"] is False


def test_activate_flag_without_data_returns_400(client):
    token = _register_and_login(client, email="noflag@example.com")
    r = client.patch(
        "/api/v1/auth/me/tenant",
        headers=_auth(token),
        json={"use_new_pricing": True},
    )
    assert r.status_code == 400
    assert "Preisliste" in r.json()["detail"]


def test_activate_flag_with_active_pricelist_succeeds(client):
    from app.core import database
    token = _register_and_login(client, email="okflag@example.com")
    tenant_id = _tenant_id(client, token)
    s = database.SessionLocal()
    try:
        from app.models.user import User
        u = s.query(User).filter(User.tenant_id == tenant_id).first()
        s.add(SupplierPriceList(
            tenant_id=tenant_id,
            supplier_name="K",
            list_name="L",
            valid_from=date(2026, 1, 1),
            source_file_path="/tmp/y.pdf",
            source_file_hash="h3",
            status=PricelistStatus.APPROVED.value,
            is_active=True,
            uploaded_by_user_id=u.id,
        ))
        s.commit()
    finally:
        s.close()
    r = client.patch(
        "/api/v1/auth/me/tenant",
        headers=_auth(token),
        json={"use_new_pricing": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["use_new_pricing"] is True


def test_deactivate_flag_always_succeeds(client):
    """Ausschalten braucht keinen Vorab-Check."""
    from app.core import database
    token = _register_and_login(client, email="off@example.com")
    tenant_id = _tenant_id(client, token)
    # manuell aktivieren (via DB)
    s = database.SessionLocal()
    try:
        from app.models.tenant import Tenant
        t = s.get(Tenant, tenant_id)
        t.use_new_pricing = True
        s.commit()
    finally:
        s.close()
    r = client.patch(
        "/api/v1/auth/me/tenant",
        headers=_auth(token),
        json={"use_new_pricing": False},
    )
    assert r.status_code == 200
    assert r.json()["use_new_pricing"] is False
