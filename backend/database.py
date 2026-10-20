"""Conexões SQLite locais ou PostgreSQL (DATABASE_URL) e transações."""
import os
import re
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path

from .layout import enforce_floor_prices, seed_rooms
from .migrations import remove_categories

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_TABLES = {"usuarios", "hospedes", "enderecos", "quartos", "reservas",
                   "acompanhantes", "pagamentos", "auditoria"}
INSERT_TABLE = re.compile(r"^\s*INSERT\s+INTO\s+([a-z_]+)\b", re.IGNORECASE)

try:
    import psycopg
    PostgresIntegrityError = psycopg.IntegrityError
    PostgresOperationalError = psycopg.OperationalError
except ImportError:
    psycopg = None

    class PostgresIntegrityError(Exception):
        pass

    class PostgresOperationalError(Exception):
        pass


class PostgresRow(Mapping):
    """Compatibilidade com sqlite3.Row: aceita nomes, índices e dict(row)."""

    def __init__(self, columns, values):
        self.columns, self.values = columns, values

    def __getitem__(self, key):
        return self.values[key] if isinstance(key, int) else self.values[self.columns.index(key)]

    def __iter__(self):
        return iter(self.columns)

    def __len__(self):
        return len(self.columns)


class PostgresCursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor, self.lastrowid = cursor, lastrowid
        self.columns = tuple(col.name for col in cursor.description) if cursor.description else ()

    def fetchone(self):
        row = self.cursor.fetchone()
        return None if row is None else PostgresRow(self.columns, row)

    def fetchall(self):
        return [PostgresRow(self.columns, row) for row in self.cursor.fetchall()]

    def __iter__(self):
        for row in self.cursor:
            yield PostgresRow(self.columns, row)


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        match = INSERT_TABLE.match(sql)
        returns_id = bool(match and match.group(1).lower() in IDENTITY_TABLES and
                          "RETURNING" not in sql.upper())
        cursor = self.connection.execute(sql.replace("?", "%s") + (" RETURNING id" if returns_id else ""), params)
        lastrowid = cursor.fetchone()[0] if returns_id else None
        return PostgresCursor(cursor, lastrowid)

    def executemany(self, sql, params):
        with self.connection.cursor() as cursor:
            cursor.executemany(sql.replace("?", "%s"), params)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def database_path():
    return Path(os.getenv("COLONIA_DB", str(ROOT / "data" / "colonia.sqlite3")))


def connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        if not url.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL deve ser uma URL PostgreSQL.")
        if psycopg is None:
            raise RuntimeError("Instale psycopg para usar DATABASE_URL.")
        return PostgresConnection(psycopg.connect(url, connect_timeout=10))
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
        if isinstance(connection, PostgresConnection):
            # Serializa alterações como o BEGIN IMMEDIATE do SQLite. Isto mantém
            # a verificação de conflito de reservas atômica entre instâncias.
            if write:
                connection.execute("SELECT pg_advisory_xact_lock(67202601)").fetchone()
        else:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize():
    if os.getenv("DATABASE_URL", "").strip():
        with transaction(write=True) as connection:
            schema = (Path(__file__).parent / "schema_postgres.sql").read_text(encoding="utf-8")
            for statement in schema.split(";"):
                if statement.strip():
                    connection.execute(statement)
            seed_rooms(connection)
            enforce_floor_prices(connection)
        return
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
