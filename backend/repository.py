"""DAO: consultas parametrizadas e mapeamento das entidades."""
from fastapi import HTTPException

from . import clock

TABLES = {"hospedes", "enderecos", "quartos", "reservas", "acompanhantes", "pagamentos", "usuarios"}


class Repository:
    def __init__(self, connection):
        self.db = connection

    def get(self, table, record_id):
        assert table in TABLES
        row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Registro não encontrado.")
        return dict(row)

    def insert(self, table, values):
        assert table in TABLES
        # Chaves são produzidas exclusivamente pelos DTOs/serviços, nunca por JSON arbitrário.
        columns = ",".join(values)
        marks = ",".join("?" for _ in values)
        return self.db.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values())).lastrowid

    def update(self, table, record_id, values):
        assert table in TABLES
        assignments = ",".join(f"{key}=?" for key in values)
        self.db.execute(f"UPDATE {table} SET {assignments} WHERE id=?", (*values.values(), record_id))

    def audit(self, user_id, action, entity, record_id):
        self.db.execute("INSERT INTO auditoria(usuario_id,acao,entidade,registro_id) VALUES (?,?,?,?)",
                        (user_id, action, entity, record_id))

    def conflicting(self, room_id, start, end, ignore_id=0):
        return self.db.execute("""SELECT id FROM reservas WHERE quarto_id=? AND id<>?
            AND ((status IN ('CONFIRMADA','HOSPEDADA') AND entrada<? AND saida>?)
            OR (status='HOSPEDADA' AND saida<=?)) LIMIT 1""",
                               (room_id, ignore_id, str(end), str(start), clock.today().isoformat())).fetchone() is not None

    def paid(self, reservation_id):
        return self.db.execute("SELECT COALESCE(SUM(valor_centavos),0) FROM pagamentos WHERE reserva_id=? AND status='PAGO'",
                               (reservation_id,)).fetchone()[0]


def mask_cpf(value):
    return f"***.{value[3:6]}.{value[6:9]}-**"


def money(value):
    return round(value / 100, 2)


def serialize_room(record):
    record = dict(record)
    record["valor_diaria"] = money(record.pop("diaria_centavos"))
    return record


def serialize_payment(record):
    record = dict(record)
    record["valor"] = money(record.pop("valor_centavos"))
    return record


def reservation_details(repo, record_id):
    record = repo.get("reservas", record_id)
    guest = repo.get("hospedes", record["hospede_id"])
    room = repo.get("quartos", record["quarto_id"])
    record.update(hospede_nome=guest["nome"], quarto_numero=room["numero"], predio=room["predio"])
    for field in ("diaria", "desconto", "total"):
        record["valor_" + field if field != "desconto" else "desconto"] = money(record.pop(field + "_centavos"))
    paid = repo.paid(record_id)
    record["valor_pago"] = money(paid)
    record["saldo"] = round(record["valor_total"] - record["valor_pago"], 2)
    record["acompanhantes"] = [dict(row) for row in repo.db.execute("SELECT id,nome FROM acompanhantes WHERE reserva_id=?", (record_id,))]
    record["pagamentos"] = [serialize_payment(row) for row in repo.db.execute("SELECT * FROM pagamentos WHERE reserva_id=? ORDER BY id DESC", (record_id,))]
    return record
