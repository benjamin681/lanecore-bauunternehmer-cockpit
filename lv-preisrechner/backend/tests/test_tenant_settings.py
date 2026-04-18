"""Tests: Tenant-Einstellungen (Stundensatz, Zuschläge) editierbar."""


def test_update_tenant_settings(client):
    # Register
    r = client.post(
        "/api/v1/auth/register",
        json={
            "firma": "Testbetrieb",
            "email": "settings@test.de",
            "password": "geheim12345",
        },
    )
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    # Defaults
    r = client.get("/api/v1/auth/me", headers=H)
    assert r.json()["stundensatz_eur"] == 46.0
    assert r.json()["bgk_prozent"] == 10.0

    # Update
    r = client.patch(
        "/api/v1/auth/me/tenant",
        json={
            "firma": "Neuer Name GmbH",
            "stundensatz_eur": 52.5,
            "bgk_prozent": 12.0,
            "wg_prozent": 6.0,
        },
        headers=H,
    )
    assert r.status_code == 200
    me = r.json()
    assert me["firma"] == "Neuer Name GmbH"
    assert me["stundensatz_eur"] == 52.5
    assert me["bgk_prozent"] == 12.0
    assert me["agk_prozent"] == 12.0  # nicht geändert
    assert me["wg_prozent"] == 6.0


def test_update_tenant_validation(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"firma": "X", "email": "val@test.de", "password": "geheim12345"},
    )
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Negative Werte abgelehnt
    r = client.patch(
        "/api/v1/auth/me/tenant",
        json={"stundensatz_eur": -5},
        headers=H,
    )
    assert r.status_code == 422

    # Überschießende Prozente abgelehnt
    r = client.patch(
        "/api/v1/auth/me/tenant",
        json={"bgk_prozent": 150},
        headers=H,
    )
    assert r.status_code == 422


def test_tenant_update_braucht_auth(client):
    r = client.patch("/api/v1/auth/me/tenant", json={"stundensatz_eur": 50})
    assert r.status_code == 401
