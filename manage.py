"""Administração local. Nenhuma senha padrão é distribuída com o projeto."""
import argparse
import getpass
import os
import sqlite3
from datetime import timedelta
from pathlib import Path

from backend.database import initialize, transaction, connect
from backend import clock
from backend.models import Hospede, Reserva
from backend.security import hash_password
from backend.services import CatalogService, ReservationService


def create_admin(only_if_empty=False):
    initialize()
    with transaction() as db:
        if only_if_empty and db.execute("SELECT 1 FROM usuarios WHERE ativo=1").fetchone():
            return
    print("Criação de conta da recepção (a senha não aparece enquanto você digita).")
    login = (os.getenv("COLONIA_ADMIN_LOGIN") or input("Usuário: ")).strip().lower()
    name = (os.getenv("COLONIA_ADMIN_NAME") or input("Nome: ")).strip()
    password = os.getenv("COLONIA_ADMIN_PASSWORD") or getpass.getpass("Senha (mínimo de 12 caracteres): ")
    if not login or not name or len(password) < 12 or len(password) > 200:
        raise SystemExit("Informe usuário, nome e uma senha de 12 a 200 caracteres.")
    if not os.getenv("COLONIA_ADMIN_PASSWORD") and password != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não coincidem.")
    with transaction(write=True) as db:
        if db.execute("SELECT 1 FROM usuarios WHERE login=?", (login,)).fetchone():
            raise SystemExit("Usuário já existe. Escolha outro login ou use a troca de senha no sistema.")
        db.execute("INSERT INTO usuarios(nome,login,senha_hash) VALUES (?,?,?)", (name, login, hash_password(password)))
    print("Conta criada. Você já pode entrar no ColôniaWeb.")


def demo():
    initialize()
    with transaction(write=True) as db:
        if db.execute("SELECT 1 FROM hospedes LIMIT 1").fetchone() or db.execute("SELECT 1 FROM reservas LIMIT 1").fetchone():
            raise SystemExit("Os exemplos só podem ser carregados sem hóspedes e reservas. Nenhum dado foi alterado.")
        user = db.execute("SELECT id FROM usuarios WHERE ativo=1 ORDER BY id LIMIT 1").fetchone()
        if not user:
            raise SystemExit("Crie uma conta com python manage.py admin primeiro.")
        catalog = CatalogService(db, user[0])
        for name, cpf in (("Hóspede Demonstração A", "52998224725"), ("Hóspede Demonstração B", "11144477735")):
            catalog.save_guest(Hospede(nome=name, cpf=cpf, nascimento="1990-01-01", email="demo@example.com", telefone="11999999999",
                observacoes="Dados inteiramente fictícios para demonstração acadêmica.",
                endereco={"cep":"01001000","logradouro":"Rua Exemplo","numero":"100","bairro":"Centro","cidade":"Cidade Exemplo","estado":"SP"}))
        service=ReservationService(db,user[0])
        today = clock.today()
        first = db.execute("SELECT id FROM quartos WHERE predio=1 AND numero=101").fetchone()[0]
        second = db.execute("SELECT id FROM quartos WHERE predio=1 AND numero=201").fetchone()[0]
        guest_ids = [row[0] for row in db.execute("SELECT id FROM hospedes ORDER BY id DESC LIMIT 2").fetchall()][::-1]
        service.save(Reserva(hospede_id=guest_ids[0],quarto_id=first,entrada=today,saida=today+timedelta(days=2),acompanhantes=[{"nome":"Acompanhante Demonstração"}]))
        service.save(Reserva(hospede_id=guest_ids[1],quarto_id=second,entrada=today+timedelta(days=3),saida=today+timedelta(days=5)))
    print("Exemplos fictícios criados: 2 hóspedes e 2 reservas nos 14 quartos já cadastrados.")


def backup(destination):
    if os.getenv("DATABASE_URL", "").strip():
        raise SystemExit("O comando backup atende somente SQLite. Para PostgreSQL, use pg_dump com a URL externa do Render.")
    path=Path(destination)
    if path.exists():
        raise SystemExit("O destino já existe. Escolha um nome novo para preservar o backup anterior.")
    path.parent.mkdir(parents=True,exist_ok=True)
    source=connect()
    target=sqlite3.connect(path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    print(f"Backup criado: {path.resolve()}")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Administração do ColôniaWeb")
    parser.add_argument("command",choices=["admin","ensure-admin","demo","init","backup"])
    parser.add_argument("destination",nargs="?")
    args=parser.parse_args()
    if args.command in ("admin","ensure-admin"):
        create_admin(args.command=="ensure-admin")
    elif args.command=="demo":
        demo()
    elif args.command=="backup":
        if not args.destination: parser.error("Informe o destino do backup.")
        backup(args.destination)
    else:
        initialize()
        print("Banco inicializado.")
