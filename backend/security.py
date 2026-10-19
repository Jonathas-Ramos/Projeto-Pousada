"""Sessões opacas, cookies HttpOnly, CSRF e senhas PBKDF2 com salt único."""
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Header, HTTPException, Request

from .database import transaction

COOKIE = "colonia_session"
ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password):
    salt = secrets.token_hex(16)
    result = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${result}"


def verify_password(password, encoded):
    algorithm, iterations, salt, expected = encoded.split("$")
    result = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    return algorithm == "pbkdf2_sha256" and hmac.compare_digest(result, expected)


def authenticate(login, password, client_ip):
    now = int(time.time())
    # IP + conta: limita força bruta por origem e por login sem guardar dados em logs.
    keys = [digest("ip:" + client_ip), digest("login:" + login.lower())]
    with transaction(write=True) as db:
        db.execute("DELETE FROM tentativas_login WHERE inicio<?", (now - 900,))
        for key in keys:
            row = db.execute("SELECT quantidade FROM tentativas_login WHERE chave=?", (key,)).fetchone()
            if row and row[0] >= 10:
                raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
        user = db.execute("SELECT * FROM usuarios WHERE login=? AND ativo=1", (login.lower(),)).fetchone()
        if user:
            valid = verify_password(password, user["senha_hash"])
        else:
            hashlib.pbkdf2_hmac("sha256", password.encode(), b"colonia-padding", ITERATIONS)
            valid = False
        if not valid:
            for key in keys:
                db.execute("""INSERT INTO tentativas_login(chave,quantidade,inicio) VALUES (?,1,?)
                    ON CONFLICT(chave) DO UPDATE SET quantidade=quantidade+1""", (key, now))
        else:
            db.execute("DELETE FROM sessoes WHERE expira<?", (now,))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessoes VALUES (?,?,?,?)", (digest(token), user["id"], csrf, now + SESSION_SECONDS))
    if not valid:
        raise HTTPException(401, "Login ou senha incorretos.")
    return {"id": user["id"], "nome": user["nome"], "csrf": csrf}, token


def require_user(request: Request, csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")):
    token = request.cookies.get(COOKIE, "")
    with transaction() as db:
        row = db.execute("""SELECT u.id,u.nome,s.csrf FROM sessoes s JOIN usuarios u ON u.id=s.usuario_id
            WHERE s.token_hash=? AND s.expira>? AND u.ativo=1""", (digest(token), int(time.time()))).fetchone()
    if row is None:
        raise HTTPException(401, "Entre novamente para continuar.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not hmac.compare_digest(csrf_token or "", row["csrf"]):
            raise HTTPException(403, "Solicitação inválida. Atualize a página.")
    return dict(row)


def secure_cookie():
    return os.getenv("COLONIA_SECURE_COOKIE", "0") == "1"
