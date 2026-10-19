"""Factory de conexões e unidade de trabalho SQLite.

BEGIN IMMEDIATE serializa a validação e a gravação das reservas/pagamentos,
impedindo que duas requisições aprovem simultaneamente o mesmo recurso.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .layout import enforce_floor_prices, seed_rooms
from .migrations import remove_categories

ROOT = Path(__file__).resolve().parents[1]


def database_path():
    return Path(os.getenv("COLONIA_DB", str(ROOT / "data" / "colonia.sqlite3")))


def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=15000")
    return connection


@contextmanager
def transaction(write=False):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize():
    connection = connect()
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        # O rebuild da tabela antiga de quartos preserva os IDs referenciados por reservas.
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        connection.execute("BEGIN IMMEDIATE")
        try:
            remove_categories(connection)
            seed_rooms(connection)
            enforce_floor_prices(connection)
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise sqlite3.IntegrityError("Migração produziria relacionamentos inválidos.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()
