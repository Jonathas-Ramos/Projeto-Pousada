"""Inicialização e configuração do serviço gratuito no Render."""
import sys

import pytest
from fastapi.testclient import TestClient

import start
from backend.config import allowed_hosts, expected_origin
from backend.database import transaction
from backend.main import app


def test_render_host_and_public_origin(monkeypatch):
    monkeypatch.delenv("COLONIA_HOSTS", raising=False)
    monkeypatch.delenv("COLONIA_PUBLIC_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "coloniaweb-exemplo.onrender.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://coloniaweb-exemplo.onrender.com")
    assert allowed_hosts() == ["coloniaweb-exemplo.onrender.com"]
    assert expected_origin("http://testserver/") == "https://coloniaweb-exemplo.onrender.com"
    monkeypatch.setenv("COLONIA_PUBLIC_URL", "https://meu-dominio.example/")
    assert expected_origin("http://testserver/") == "https://meu-dominio.example"


def test_render_login_origin(tmp_path, monkeypatch):
    from backend.security import hash_password

    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "render.sqlite3"))
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://coloniaweb-exemplo.onrender.com")
    monkeypatch.delenv("COLONIA_PUBLIC_URL", raising=False)
    with TestClient(app) as client:
        with transaction(write=True) as db:
            db.execute("INSERT INTO usuarios(nome,login,senha_hash) VALUES (?,?,?)",
                       ("Recepção", "admin", hash_password("SenhaTeste123!")))
        response = client.post("/api/auth/login", json={"login": "admin", "senha": "SenhaTeste123!"},
                               headers={"Origin": "https://coloniaweb-exemplo.onrender.com"})
        assert response.status_code == 200
        assert client.post("/api/auth/login", json={"login": "admin", "senha": "SenhaTeste123!"},
                           headers={"Origin": "https://outro.example"}).status_code == 403


def test_start_bootstraps_admin_and_uses_render_port(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "startup.sqlite3"))
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://coloniaweb-exemplo.onrender.com")
    monkeypatch.setenv("COLONIA_ADMIN_LOGIN", "edusilva")
    monkeypatch.setenv("COLONIA_ADMIN_NAME", "eduardo")
    monkeypatch.setenv("COLONIA_ADMIN_PASSWORD", "SenhaTeste123!")
    monkeypatch.setenv("PORT", "10000")
    calls = []
    monkeypatch.setattr(start.os, "execv", lambda path, args: calls.append((path, args)))

    start.main()
    start.main()
    with transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 1
        assert db.execute("SELECT nome FROM usuarios WHERE login='edusilva'").fetchone()[0] == "eduardo"
        assert db.execute("SELECT COUNT(*) FROM quartos").fetchone()[0] == 14
    assert len(calls) == 2
    assert calls[0] == (sys.executable, [sys.executable, "-m", "uvicorn", "backend.main:app",
                                       "--host", "0.0.0.0", "--port", "10000", "--workers", "1"])


def test_render_requires_admin_password(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://coloniaweb-exemplo.onrender.com")
    monkeypatch.delenv("COLONIA_ADMIN_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="COLONIA_ADMIN_PASSWORD"):
        start.main()


def test_start_adds_configured_login_when_another_admin_exists(tmp_path, monkeypatch):
    from backend.database import initialize
    from backend.security import hash_password

    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "existing.sqlite3"))
    initialize()
    with transaction(write=True) as db:
        db.execute("INSERT INTO usuarios(nome,login,senha_hash) VALUES (?,?,?)",
                   ("Recepção", "admin", hash_password("SenhaAntiga123!")))
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://coloniaweb-exemplo.onrender.com")
    monkeypatch.setenv("COLONIA_ADMIN_LOGIN", "edusilva")
    monkeypatch.setenv("COLONIA_ADMIN_NAME", "eduardo")
    monkeypatch.setenv("COLONIA_ADMIN_PASSWORD", "SenhaTeste123!")
    monkeypatch.setattr(start.os, "execv", lambda path, args: None)
    start.main()
    with transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 2
        assert db.execute("SELECT ativo FROM usuarios WHERE login='edusilva'").fetchone()[0] == 1
