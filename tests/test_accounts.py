"""Cadastro público, login e recuperação de senha sem serviço de e-mail."""
from fastapi.testclient import TestClient

from backend.database import transaction
from backend.main import app


ACCOUNT = {
    "nome": "Eduardo Silva", "login": "EduSilva",
    "senha": "SenhaDeTeste123!", "confirmar_senha": "SenhaDeTeste123!",
}


def test_signup_login_logout_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("COLONIA_SELF_REGISTER", "1")
    monkeypatch.setenv("COLONIA_SECURE_COOKIE", "0")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/auth/registration").json() == {"enabled": True}
        html = client.get("/").text
        assert "Esqueci a senha" in html and "Não tenho cadastro" in html
        assert 'id="login-form"' in html and 'id="register-form"' in html and 'id="reset-form"' in html
        assert client.get("/api/auth/first-access").json() == {"required": False, "enabled": False}
        assert client.post("/api/auth/register", json={**ACCOUNT, "confirmar_senha": "SenhaErrada123!"}).status_code == 400
        assert client.post("/api/auth/register", json=ACCOUNT,
                           headers={"Origin": "https://outro.example"}).status_code == 403
        created = client.post("/api/auth/register", json=ACCOUNT)
        assert created.status_code == 201, created.text
        recovery_code = created.json()["recovery_code"]
        assert len(recovery_code) >= 30
        assert client.post("/api/auth/register", json=ACCOUNT).status_code == 409
        with transaction() as db:
            row = db.execute("SELECT login,senha_hash FROM usuarios").fetchone()
            assert row["login"] == "edusilva" and ACCOUNT["senha"] not in row["senha_hash"]
            assert db.execute("SELECT codigo_hash FROM codigos_recuperacao").fetchone()[0] != recovery_code

        signed_in = client.post("/api/auth/login", json={"login": "EduSilva", "senha": ACCOUNT["senha"]})
        assert signed_in.status_code == 200
        wrong = client.post("/api/auth/reset-password", json={
            "login": "edusilva", "codigo": "incorreto", "nova_senha": "NovaSenhaTeste123!",
            "confirmar_senha": "NovaSenhaTeste123!",
        })
        assert wrong.status_code == 400
        assert client.post("/api/auth/reset-password", json={
            "login": "edusilva", "codigo": recovery_code, "nova_senha": "NovaSenhaTeste123!",
            "confirmar_senha": "SenhaDiferente123!",
        }).status_code == 400
        reset = client.post("/api/auth/reset-password", json={
            "login": "edusilva", "codigo": recovery_code, "nova_senha": "NovaSenhaTeste123!",
            "confirmar_senha": "NovaSenhaTeste123!",
        })
        assert reset.status_code == 200, reset.text
        assert reset.json()["recovery_code"] != recovery_code
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json={"login": "edusilva", "senha": ACCOUNT["senha"]}).status_code == 401
        assert client.post("/api/auth/reset-password", json={
            "login": "edusilva", "codigo": recovery_code, "nova_senha": "OutraSenhaTeste123!",
            "confirmar_senha": "OutraSenhaTeste123!",
        }).status_code == 400
        signed_in = client.post("/api/auth/login", json={"login": "edusilva", "senha": "NovaSenhaTeste123!"})
        assert signed_in.status_code == 200
        assert client.post("/api/auth/logout", headers={"X-CSRF-Token": signed_in.json()["csrf"]}).status_code == 200
        assert client.get("/api/auth/me").status_code == 401


def test_authenticated_user_can_create_and_rotate_recovery_code(tmp_path, monkeypatch):
    from backend.security import hash_password

    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "legacy-user.sqlite3"))
    monkeypatch.setenv("COLONIA_SECURE_COOKIE", "0")
    with TestClient(app) as client:
        with transaction(write=True) as db:
            db.execute("INSERT INTO usuarios(nome,login,senha_hash) VALUES (?,?,?)",
                       ("Usuário antigo", "antigo", hash_password("SenhaAntiga123!")))
        signed_in = client.post("/api/auth/login", json={"login": "antigo", "senha": "SenhaAntiga123!"})
        headers = {"X-CSRF-Token": signed_in.json()["csrf"]}
        assert client.post("/api/auth/recovery-code", json={"senha_atual": "SenhaAntiga123!"}).status_code == 403
        assert client.post("/api/auth/recovery-code", json={"senha_atual": "errada"}, headers=headers).status_code == 400
        first = client.post("/api/auth/recovery-code", json={"senha_atual": "SenhaAntiga123!"}, headers=headers)
        second = client.post("/api/auth/recovery-code", json={"senha_atual": "SenhaAntiga123!"}, headers=headers)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["recovery_code"] != second.json()["recovery_code"]


def test_public_registration_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "disabled.sqlite3"))
    monkeypatch.delenv("COLONIA_SELF_REGISTER", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/auth/registration").json() == {"enabled": False}
        assert client.post("/api/auth/register", json=ACCOUNT).status_code == 403


def test_multiple_people_can_register_and_recovery_is_limited(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "multiple.sqlite3"))
    monkeypatch.setenv("COLONIA_SELF_REGISTER", "1")
    with TestClient(app) as client:
        first = client.post("/api/auth/register", json=ACCOUNT)
        second = client.post("/api/auth/register", json={**ACCOUNT, "nome": "Ana Silva", "login": "AnaSilva"})
        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["recovery_code"] != second.json()["recovery_code"]
        with transaction() as db:
            assert db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 2
        bad = {"login": "AnaSilva", "codigo": "incorreto", "nova_senha": "NovaSenhaTeste123!",
               "confirmar_senha": "NovaSenhaTeste123!"}
        for _ in range(10):
            assert client.post("/api/auth/reset-password", json=bad).status_code == 400
        assert client.post("/api/auth/reset-password", json={**bad, "codigo": second.json()["recovery_code"]}).status_code == 429
