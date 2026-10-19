"""O código secreto habilita somente a criação da primeira conta pela página."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.database import initialize, transaction
from backend.main import app
from backend.security import create_first_user


SETUP_CODE = "CodigoDeTesteSeguro123!"
FIRST_USER = {
    "nome": "Eduardo Silva",
    "login": "EduSilva",
    "senha": "SenhaDeTeste123!",
    "confirmar_senha": "SenhaDeTeste123!",
    "codigo": SETUP_CODE,
}


@pytest.fixture
def setup_client(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "first-access.sqlite3"))
    monkeypatch.setenv("COLONIA_SETUP_CODE", SETUP_CODE)
    monkeypatch.setenv("COLONIA_SECURE_COOKIE", "0")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("COLONIA_PUBLIC_URL", raising=False)
    with TestClient(app) as client:
        yield client


def test_first_access_creates_account_and_closes_registration(setup_client):
    client = setup_client
    assert client.get("/api/auth/first-access").json() == {"required": True, "enabled": True}
    response = client.post("/api/auth/first-access", json=FIRST_USER, headers={"Origin": "http://testserver"})
    assert response.status_code == 201, response.text
    assert response.json()["nome"] == "Eduardo Silva"
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/auth/first-access").json() == {"required": False, "enabled": False}
    assert client.post("/api/auth/first-access", json=FIRST_USER).status_code == 409
    with transaction() as db:
        assert db.execute("SELECT login FROM usuarios").fetchone()[0] == "edusilva"
        assert db.execute("SELECT acao FROM auditoria").fetchone()[0] == "CRIAR_PRIMEIRO_ACESSO"


def test_login_page_offers_first_access_without_server_command(setup_client):
    response = setup_client.get("/")
    assert response.status_code == 200
    assert 'id="setup-form"' in response.text
    assert "Código de ativação" in response.text
    assert "python manage.py admin" not in response.text


def test_first_access_rejects_wrong_code_password_confirmation_and_origin(setup_client):
    client = setup_client
    assert client.post("/api/auth/first-access", json={**FIRST_USER, "codigo": "CodigoErrado123456!"}).status_code == 403
    assert client.post("/api/auth/first-access", json={**FIRST_USER, "codigo": "código inválido"}).status_code == 403
    assert client.post("/api/auth/first-access", json={**FIRST_USER, "confirmar_senha": "OutraSenha123!"}).status_code == 400
    assert client.post("/api/auth/first-access", json=FIRST_USER,
                       headers={"Origin": "https://outro.example"}).status_code == 403
    with transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0


def test_first_access_requires_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "no-code.sqlite3"))
    monkeypatch.delenv("COLONIA_SETUP_CODE", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/auth/first-access").json() == {"required": True, "enabled": False}
        assert client.post("/api/auth/first-access", json=FIRST_USER).status_code == 503


def test_first_access_limits_wrong_codes(setup_client):
    client = setup_client
    wrong = {**FIRST_USER, "codigo": "CodigoErrado123456!"}
    for _ in range(10):
        assert client.post("/api/auth/first-access", json=wrong).status_code == 403
    assert client.post("/api/auth/first-access", json=FIRST_USER).status_code == 429


def test_only_one_concurrent_first_account(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "race.sqlite3"))
    monkeypatch.setenv("COLONIA_SETUP_CODE", SETUP_CODE)
    initialize()

    def register():
        try:
            return create_first_user("Eduardo Silva", "edusilva", "SenhaDeTeste123!", SETUP_CODE, "127.0.0.1")[0]
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: register(), range(2)))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert 409 in outcomes
    with transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 1
