import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import clock, models
from .config import allowed_hosts, expected_origin
from .database import PostgresIntegrityError, PostgresOperationalError, initialize, transaction
from .repository import Repository, mask_cpf, money, reservation_details, serialize_room
from .security import COOKIE, SESSION_SECONDS, authenticate, create_first_user, digest, first_access_status, hash_password, register_user, registration_enabled, require_user, reset_password, rotate_recovery_code, secure_cookie, verify_password
from .services import CatalogService, ReservationService


@asynccontextmanager
async def lifespan(app):
    # Pesquisas por CPF podem aparecer na query string; não gravar access logs brutos.
    logging.getLogger("uvicorn.access").disabled = True
    initialize()
    yield


app = FastAPI(title="ColôniaWeb API", version="1.0.0", description="Gestão de hospedagens, sem serviços adicionais. Valores em BRL; datas ISO 8601.",
              lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())
User = Annotated[dict, Depends(require_user)]
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


@app.middleware("http")
async def security_headers(request, call_next):
    try:
        content_length = int(request.headers.get("content-length", "0") or 0)
    except ValueError:
        return JSONResponse({"detail": "Tamanho da solicitação inválido."}, status_code=400)
    if content_length > 131072:
        return JSONResponse({"detail": "Solicitação muito grande."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    if request.url.path == "/docs":
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; frame-ancestors 'none'"
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    if secure_cookie():
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Não devolve o corpo recebido: pode conter CPF ou senha.
    fields = [{"campo": ".".join(map(str, item["loc"][1:])), "erro": item["msg"]} for item in error.errors()]
    return JSONResponse({"detail": "Revise os campos informados.", "campos": fields}, status_code=422)


@app.exception_handler(sqlite3.IntegrityError)
@app.exception_handler(PostgresIntegrityError)
async def integrity_error(request, error):
    text = str(error)
    constraint = getattr(getattr(error, "diag", None), "constraint_name", "")
    message = "Operação viola um vínculo ou uma regra do cadastro."
    if "hospedes.cpf" in text or constraint == "hospedes_cpf_key":
        message = "Já existe um hóspede com esse CPF."
    elif "quartos.predio" in text or constraint == "quartos_predio_numero_key":
        message = "Já existe este número de quarto neste prédio."
    return JSONResponse({"detail": message}, status_code=409)


@app.exception_handler(sqlite3.OperationalError)
@app.exception_handler(PostgresOperationalError)
async def database_error(request, error):
    return JSONResponse({"detail": "Banco temporariamente indisponível. Tente novamente."}, status_code=503)


@app.get("/api/health", tags=["Sistema"])
def health():
    with transaction() as db:
        db.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.post("/api/auth/login", tags=["Autenticação"])
def login(dto: models.Login, request: Request, response: Response):
    origin = request.headers.get("origin")
    if origin and origin != expected_origin(str(request.base_url)):
        raise HTTPException(403, "Origem inválida.")
    user, token = authenticate(dto.login, dto.senha, request.client.host if request.client else "local")
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=secure_cookie(), samesite="strict")
    return user


@app.get("/api/auth/registration", tags=["Autenticação"])
def registration_status():
    return {"enabled": registration_enabled()}


@app.post("/api/auth/register", status_code=201, tags=["Autenticação"])
def register(dto: models.Cadastro, request: Request):
    origin = request.headers.get("origin")
    if origin and origin != expected_origin(str(request.base_url)):
        raise HTTPException(403, "Origem inválida.")
    if dto.senha != dto.confirmar_senha:
        raise HTTPException(400, "As senhas não coincidem.")
    return register_user(dto.nome, dto.login, dto.senha, request.client.host if request.client else "local")


@app.post("/api/auth/reset-password", tags=["Autenticação"])
def recover_password(dto: models.RecuperarSenha, request: Request):
    origin = request.headers.get("origin")
    if origin and origin != expected_origin(str(request.base_url)):
        raise HTTPException(403, "Origem inválida.")
    if dto.nova_senha != dto.confirmar_senha:
        raise HTTPException(400, "As senhas não coincidem.")
    return reset_password(dto.login, dto.codigo, dto.nova_senha,
                          request.client.host if request.client else "local")


@app.post("/api/auth/recovery-code", tags=["Autenticação"])
def generate_recovery_code(dto: models.GerarCodigoRecuperacao, user: User):
    return rotate_recovery_code(user["id"], dto.senha_atual)


@app.get("/api/auth/first-access", tags=["Autenticação"])
def first_access():
    return first_access_status()


@app.post("/api/auth/first-access", status_code=201, tags=["Autenticação"])
def register_first_user(dto: models.PrimeiroAcesso, request: Request, response: Response):
    origin = request.headers.get("origin")
    if origin and origin != expected_origin(str(request.base_url)):
        raise HTTPException(403, "Origem inválida.")
    if dto.senha != dto.confirmar_senha:
        raise HTTPException(400, "As senhas não coincidem.")
    user, token = create_first_user(dto.nome, dto.login, dto.senha, dto.codigo,
                                    request.client.host if request.client else "local")
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=secure_cookie(), samesite="strict")
    return user


@app.get("/api/auth/me", tags=["Autenticação"])
def me(user: User):
    return user


@app.post("/api/auth/logout", tags=["Autenticação"])
def logout(request: Request, response: Response, user: User):
    with transaction(write=True) as db:
        db.execute("DELETE FROM sessoes WHERE token_hash=?", (digest(request.cookies.get(COOKIE, "")),))
    response.delete_cookie(COOKIE)
    return {"mensagem": "Sessão encerrada."}


@app.put("/api/auth/senha", tags=["Autenticação"])
def change_password(dto: models.TrocaSenha, user: User, response: Response):
    with transaction(write=True) as db:
        row = db.execute("SELECT senha_hash FROM usuarios WHERE id=?", (user["id"],)).fetchone()
        if not verify_password(dto.senha_atual, row[0]):
            raise HTTPException(400, "Senha atual incorreta.")
        db.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (hash_password(dto.nova_senha), user["id"]))
        db.execute("DELETE FROM sessoes WHERE usuario_id=?", (user["id"],))
    response.delete_cookie(COOKIE)
    return {"mensagem": "Senha atualizada. Entre novamente."}


@app.get("/api/hospedes", tags=["Hóspedes"])
def guests(user: User, q: str = Query("", max_length=150), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    with transaction() as db:
        where, args = "(LOWER(nome) LIKE LOWER(?) OR cpf LIKE ?)", (f"%{q}%", f"%{q}%")
        count = db.execute(f"SELECT COUNT(*) FROM hospedes WHERE {where}", args).fetchone()[0]
        rows = db.execute(f"SELECT id,nome,cpf,email,telefone,ativo FROM hospedes WHERE {where} ORDER BY nome LIMIT ? OFFSET ?", (*args, limit, offset))
        items = [{**dict(row), "cpf": mask_cpf(row["cpf"])} for row in rows]
    return {"items": items, "total": count}


@app.get("/api/hospedes/{record_id}", tags=["Hóspedes"])
def guest(record_id: int, user: User):
    with transaction() as db:
        return CatalogService(db, user["id"]).guest_details(record_id)


@app.post("/api/hospedes", status_code=201, tags=["Hóspedes"])
def create_guest(dto: models.Hospede, user: User):
    with transaction(write=True) as db:
        return CatalogService(db, user["id"]).save_guest(dto)


@app.put("/api/hospedes/{record_id}", tags=["Hóspedes"])
def update_guest(record_id: int, dto: models.Hospede, user: User):
    with transaction(write=True) as db:
        return CatalogService(db, user["id"]).save_guest(dto, record_id)


@app.delete("/api/hospedes/{record_id}", tags=["Hóspedes"])
def delete_guest(record_id: int, user: User):
    with transaction(write=True) as db:
        return CatalogService(db, user["id"]).delete("hospedes", record_id)


@app.get("/api/quartos/disponiveis", tags=["Quartos"])
def available(user: User, entrada: date, saida: date, pessoas: int = Query(1, ge=1, le=30)):
    if saida <= entrada or entrada < clock.today():
        raise HTTPException(422, "Informe um período válido, a partir de hoje.")
    with transaction() as db:
        repo = Repository(db)
        return [serialize_room(row) for row in db.execute("SELECT * FROM quartos WHERE ativo=1 AND status='DISPONIVEL' AND capacidade>=? ORDER BY predio,numero", (pessoas,))
                if not repo.conflicting(row["id"], entrada, saida)]


@app.get("/api/quartos", tags=["Quartos"])
def rooms(user: User):
    with transaction() as db:
        return [room_with_state(row) for row in db.execute("""SELECT q.*,
             EXISTS(SELECT 1 FROM reservas r WHERE r.quarto_id=q.id AND r.status='HOSPEDADA') AS ocupado
             FROM quartos q ORDER BY q.predio,q.andar,q.numero""")]


def room_with_state(row):
    item = serialize_room(row)
    item["situacao_atual"] = ("INATIVO" if not item["ativo"] else
                              "MANUTENCAO" if item["status"] == "MANUTENCAO" else
                              "OCUPADO" if item["ocupado"] else "LIVRE")
    return item


@app.get("/api/quartos/{record_id}", tags=["Quartos"])
def room(record_id: int, user: User):
    with transaction() as db:
        row = db.execute("""SELECT q.*,
            EXISTS(SELECT 1 FROM reservas r WHERE r.quarto_id=q.id AND r.status='HOSPEDADA') AS ocupado
            FROM quartos q WHERE q.id=?""", (record_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Registro não encontrado.")
        return room_with_state(row)


@app.post("/api/quartos", status_code=201, tags=["Quartos"])
def create_room(user: User):
    raise HTTPException(409, "A pousada possui 14 quartos fixos, já cadastrados em dois andares.")


@app.put("/api/quartos/{record_id}", tags=["Quartos"])
def update_room(record_id: int, dto: models.Quarto, user: User):
    with transaction(write=True) as db:
        return CatalogService(db, user["id"]).save_room(dto, record_id)


@app.delete("/api/quartos/{record_id}", tags=["Quartos"])
def delete_room(record_id: int, user: User):
    with transaction(write=True) as db:
        return CatalogService(db, user["id"]).delete("quartos", record_id)


@app.get("/api/reservas", tags=["Reservas"])
def reservations(user: User, status: str = Query("", max_length=20), q: str = Query("", max_length=150), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    with transaction() as db:
        sql = "FROM reservas r JOIN hospedes h ON h.id=r.hospede_id WHERE (?='' OR r.status=?) AND (r.codigo LIKE ? OR LOWER(h.nome) LIKE LOWER(?))"
        args = (status, status, f"%{q}%", f"%{q}%")
        total = db.execute("SELECT COUNT(*) " + sql, args).fetchone()[0]
        ids = db.execute("SELECT r.id " + sql + " ORDER BY r.entrada DESC,r.id DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
        return {"items": [reservation_details(Repository(db), row[0]) for row in ids], "total": total}


@app.post("/api/reservas/simular", tags=["Reservas"])
def quote(dto: models.Reserva, user: User, reserva_id: int | None = None):
    with transaction() as db:
        result = ReservationService(db, user["id"]).quote(dto, reserva_id)
        return {"diarias": result["diarias"], "pessoas": result["quantidade"], "valor_diaria": money(result["diaria_centavos"]), "total": money(result["total_centavos"])}


@app.get("/api/reservas/{record_id}", tags=["Reservas"])
def reservation(record_id: int, user: User):
    with transaction() as db:
        return reservation_details(Repository(db), record_id)


@app.post("/api/reservas", status_code=201, tags=["Reservas"])
def create_reservation(dto: models.Reserva, user: User):
    with transaction(write=True) as db:
        return ReservationService(db, user["id"]).save(dto)


@app.put("/api/reservas/{record_id}", tags=["Reservas"])
def update_reservation(record_id: int, dto: models.Reserva, user: User):
    with transaction(write=True) as db:
        return ReservationService(db, user["id"]).save(dto, record_id)


@app.patch("/api/reservas/{record_id}/{acao}", tags=["Reservas"])
def transition(record_id: int, acao: Literal["check-in", "check-out", "cancelar"], user: User):
    with transaction(write=True) as db:
        return ReservationService(db, user["id"]).transition(record_id, acao)


@app.delete("/api/reservas/{record_id}", tags=["Reservas"])
def cancel(record_id: int, user: User):
    """Exclusão lógica: cancela uma reserva confirmada e preserva seu histórico."""
    with transaction(write=True) as db:
        return ReservationService(db, user["id"]).transition(record_id, "cancelar")


@app.post("/api/reservas/{record_id}/pagamentos", status_code=201, tags=["Pagamentos"])
def pay(record_id: int, dto: models.Pagamento, user: User):
    with transaction(write=True) as db:
        return ReservationService(db, user["id"]).pay(record_id, dto)


@app.post("/api/pagamentos/{record_id}/estornar", tags=["Pagamentos"])
def refund(record_id: int, dto: models.Estorno, user: User):
    """Registra confirmação de estorno já efetuado externamente; não movimenta dinheiro."""
    with transaction(write=True) as db:
        return ReservationService(db, user["id"]).refund(record_id, dto)


@app.get("/api/dashboard", tags=["Painel"])
def dashboard(user: User):
    today = clock.today().isoformat()
    with transaction() as db:
        active = db.execute("SELECT COUNT(*) FROM quartos WHERE ativo=1").fetchone()[0]
        occupied = db.execute("SELECT COUNT(DISTINCT quarto_id) FROM reservas WHERE status='HOSPEDADA'").fetchone()[0]
        arrivals = db.execute("SELECT id FROM reservas WHERE entrada=? AND status='CONFIRMADA' ORDER BY id", (today,)).fetchall()
        departures = db.execute("SELECT id FROM reservas WHERE saida<=? AND status='HOSPEDADA' ORDER BY saida", (today,)).fetchall()
        return {"quartos_ativos": active, "ocupados": occupied,
                "hospedes": db.execute("SELECT COUNT(*) FROM hospedes WHERE ativo=1").fetchone()[0],
                "recebido": money(db.execute("SELECT COALESCE(SUM(valor_centavos),0) FROM pagamentos WHERE status='PAGO'").fetchone()[0]),
                "entradas": [reservation_details(Repository(db), r[0]) for r in arrivals],
                "saidas": [reservation_details(Repository(db), r[0]) for r in departures]}


@app.get("/api/auditoria", tags=["Sistema"])
def audit(user: User, limit: int = Query(100, ge=1, le=200)):
    with transaction() as db:
        return [dict(row) for row in db.execute("SELECT a.*,u.nome AS usuario FROM auditoria a LEFT JOIN usuarios u ON u.id=a.usuario_id ORDER BY a.id DESC LIMIT ?", (limit,))]


@app.get("/api/openapi.json", include_in_schema=False)
def openapi(user: User):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def docs(user: User):
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title="ColôniaWeb · API", swagger_favicon_url="/static/favicon.svg")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
