"""Smoke-Tests: Auth-Flow."""


def test_register_login_me(client):
    # Register
    r = client.post(
        "/api/v1/auth/register",
        json={
            "firma": "Trockenbau Test GmbH",
            "vorname": "Max",
            "nachname": "Mustermann",
            "email": "test@example.com",
            "password": "geheim12345",
        },
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]

    # Me
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == "test@example.com"
    assert me["firma"] == "Trockenbau Test GmbH"
    assert me["stundensatz_eur"] == 46.0

    # Login
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "geheim12345"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_register_duplicate_email(client):
    payload = {
        "firma": "A", "email": "dup@x.de", "password": "abcdefgh",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={
        "firma": "B", "email": "b@x.de", "password": "rightpass",
    })
    r = client.post("/api/v1/auth/login", json={"email": "b@x.de", "password": "wrongpass"})
    assert r.status_code == 401


def test_protected_route_without_token(client):
    r = client.get("/api/v1/lvs")
    assert r.status_code == 401
