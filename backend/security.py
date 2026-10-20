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
DEMO_SETUP_CODE = "APRESENTACAO2026"
INCREMENT_LOGIN_ATTEMPT_SQL = """INSERT INTO tentativas_login(chave,quantidade,inicio) VALUES (?,1,?)
    ON CONFLICT(chave) DO UPDATE SET quantidade=tentativas_login.quantidade+1"""


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


def issue_session(db, user_id, now):
    db.execute("DELETE FROM sessoes WHERE expira<?", (now,))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessoes VALUES (?,?,?,?)", (digest(token), user_id, csrf, now + SESSION_SECONDS))
    return token, csrf


def registration_enabled():
    return os.getenv("COLONIA_SELF_REGISTER") == "1"


def new_recovery_code():
    return secrets.token_urlsafe(24)


def register_user(name, login, password, client_ip):
    if not registration_enabled():
        raise HTTPException(403, "Cadastro público desabilitado neste servidor.")
    now = int(time.time())
    key = digest("register-ip:" + client_ip)
    login = login.lower()
    with transaction(write=True) as db:
        db.execute("DELETE FROM tentativas_login WHERE inicio<?", (now - 900,))
        row = db.execute("SELECT quantidade FROM tentativas_login WHERE chave=?", (key,)).fetchone()
        if row and row[0] >= 10:
            raise HTTPException(429, "Muitos cadastros. Aguarde 15 minutos.")
        if db.execute("SELECT 1 FROM usuarios WHERE login=?", (login,)).fetchone():
            raise HTTPException(409, "Este usuário não está disponível.")
        code = new_recovery_code()
        cursor = db.execute("INSERT INTO usuarios(nome,login,senha_hash) VALUES (?,?,?)",
                            (name, login, hash_password(password)))
        db.execute("INSERT INTO codigos_recuperacao(usuario_id,codigo_hash) VALUES (?,?)",
                   (cursor.lastrowid, digest(code)))
        db.execute("INSERT INTO auditoria(usuario_id,acao,entidade,registro_id) VALUES (?,?,?,?)",
                   (cursor.lastrowid, "CRIAR_USUARIO", "usuarios", cursor.lastrowid))
        db.execute(INCREMENT_LOGIN_ATTEMPT_SQL, (key, now))
    return {"nome": name, "login": login, "recovery_code": code}


def reset_password(login, code, new_password, client_ip):
    now = int(time.time())
    login = login.lower()
    keys = [digest("recovery-ip:" + client_ip), digest("recovery-login:" + login)]
    outcome = None
    with transaction(write=True) as db:
        db.execute("DELETE FROM tentativas_login WHERE inicio<?", (now - 900,))
        for key in keys:
            row = db.execute("SELECT quantidade FROM tentativas_login WHERE chave=?", (key,)).fetchone()
            if row and row[0] >= 10:
                raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
        row = db.execute("""SELECT u.id,c.codigo_hash FROM usuarios u
            LEFT JOIN codigos_recuperacao c ON c.usuario_id=u.id
            WHERE u.login=? AND u.ativo=1""", (login,)).fetchone()
        valid = hmac.compare_digest(digest(code), row["codigo_hash"] if row and row["codigo_hash"] else "0" * 64)
        if not valid:
            for key in keys:
                db.execute(INCREMENT_LOGIN_ATTEMPT_SQL, (key, now))
            outcome = (400, "Usuário ou código de recuperação inválido.")
        else:
            next_code = new_recovery_code()
            db.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (hash_password(new_password), row["id"]))
            db.execute("UPDATE codigos_recuperacao SET codigo_hash=? WHERE usuario_id=?",
                       (digest(next_code), row["id"]))
            db.execute("DELETE FROM sessoes WHERE usuario_id=?", (row["id"],))
            db.execute("INSERT INTO auditoria(usuario_id,acao,entidade,registro_id) VALUES (?,?,?,?)",
                       (row["id"], "RECUPERAR_SENHA", "usuarios", row["id"]))
            for key in keys:
                db.execute("DELETE FROM tentativas_login WHERE chave=?", (key,))
    if outcome:
        raise HTTPException(*outcome)
    return {"mensagem": "Senha atualizada. Entre com a nova senha.", "recovery_code": next_code}


def rotate_recovery_code(user_id, current_password):
    with transaction(write=True) as db:
        row = db.execute("SELECT senha_hash FROM usuarios WHERE id=? AND ativo=1", (user_id,)).fetchone()
        if not row or not verify_password(current_password, row["senha_hash"]):
            raise HTTPException(400, "Senha atual incorreta.")
        code = new_recovery_code()
        db.execute("""INSERT INTO codigos_recuperacao(usuario_id,codigo_hash) VALUES (?,?)
            ON CONFLICT(usuario_id) DO UPDATE SET codigo_hash=excluded.codigo_hash""", (user_id, digest(code)))
        db.execute("INSERT INTO auditoria(usuario_id,acao,entidade,registro_id) VALUES (?,?,?,?)",
                   (user_id, "GERAR_CODIGO_RECUPERACAO", "usuarios", user_id))
    return {"recovery_code": code}


def first_access_status():
    if registration_enabled():
        return {"required": False, "enabled": False}
    with transaction() as db:
        required = db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is None
    demo = os.getenv("COLONIA_DEMO_MODE") == "1"
    code = DEMO_SETUP_CODE if demo else os.getenv("COLONIA_SETUP_CODE", "").strip()
    status = {"required": required, "enabled": required and (demo or 16 <= len(code) <= 200)}
    if required and demo:
        status["demo_code"] = DEMO_SETUP_CODE
    return status


def create_first_user(name, login, password, code, client_ip):
    if registration_enabled():
        raise HTTPException(410, "Use o cadastro de usuário na página de login.")
    demo = os.getenv("COLONIA_DEMO_MODE") == "1"
    configured_code = DEMO_SETUP_CODE if demo else os.getenv("COLONIA_SETUP_CODE", "").strip()
    if not demo and not 16 <= len(configured_code) <= 200:
        raise HTTPException(503, "O primeiro acesso ainda não foi habilitado pelo responsável.")
    now = int(time.time())
    key = digest("setup:" + client_ip)
    outcome = None
    with transaction(write=True) as db:
        if db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            raise HTTPException(409, "O primeiro acesso já foi criado. Entre com sua conta.")
        db.execute("DELETE FROM tentativas_login WHERE inicio<?", (now - 900,))
        row = db.execute("SELECT quantidade FROM tentativas_login WHERE chave=?", (key,)).fetchone()
        if row and row["quantidade"] >= 10:
            outcome = (429, "Muitas tentativas. Aguarde 15 minutos.")
        elif not hmac.compare_digest(code.encode("utf-8"), configured_code.encode("utf-8")):
            db.execute(INCREMENT_LOGIN_ATTEMPT_SQL, (key, now))
            outcome = (403, "Código de ativação inválido.")
        else:
            login = login.lower()
            cursor = db.execute("INSERT INTO usuarios(nome,login,senha_hash) VALUES (?,?,?)",
                                (name, login, hash_password(password)))
            db.execute("INSERT INTO auditoria(usuario_id,acao,entidade,registro_id) VALUES (?,?,?,?)",
                       (cursor.lastrowid, "CRIAR_PRIMEIRO_ACESSO", "usuarios", cursor.lastrowid))
            db.execute("DELETE FROM tentativas_login WHERE chave=?", (key,))
            token, csrf = issue_session(db, cursor.lastrowid, now)
            user = {"id": cursor.lastrowid, "nome": name, "csrf": csrf}
    if outcome:
        raise HTTPException(*outcome)
    return user, token


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
                db.execute(INCREMENT_LOGIN_ATTEMPT_SQL, (key, now))
        else:
            token, csrf = issue_session(db, user["id"], now)
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
