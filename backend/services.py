"""Regras de negócio independentes da interface. Valores monetários em centavos."""
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from . import clock
from .repository import Repository, reservation_details, serialize_room, serialize_payment, money


def cents(value):
    return int(Decimal(str(value)) * 100)


def refuse(message):
    raise HTTPException(409, message)


class CatalogService:
    def __init__(self, db, user_id):
        self.repo = Repository(db)
        self.db, self.user_id = db, user_id

    def save_guest(self, dto, record_id=None):
        values = dto.model_dump(mode="json", exclude={"endereco"})
        if record_id:
            self.repo.get("hospedes", record_id)
            if not dto.ativo and self.db.execute("SELECT 1 FROM reservas WHERE hospede_id=? AND status IN ('CONFIRMADA','HOSPEDADA')", (record_id,)).fetchone():
                refuse("Hóspede possui reserva ativa. Finalize ou cancele antes de desativar.")
            self.repo.update("hospedes", record_id, values)
            address_id = self.db.execute("SELECT id FROM enderecos WHERE hospede_id=?", (record_id,)).fetchone()[0]
            self.repo.update("enderecos", address_id, dto.endereco.model_dump())
        else:
            record_id = self.repo.insert("hospedes", values)
            self.repo.insert("enderecos", {"hospede_id": record_id, **dto.endereco.model_dump()})
        self.repo.audit(self.user_id, "SALVAR", "hospedes", record_id)
        return self.guest_details(record_id)

    def guest_details(self, record_id):
        record = self.repo.get("hospedes", record_id)
        record["endereco"] = dict(self.db.execute("SELECT * FROM enderecos WHERE hospede_id=?", (record_id,)).fetchone())
        return record

    def save_room(self, dto, record_id):
        original = self.repo.get("quartos", record_id)
        if (dto.predio, dto.andar, dto.numero) != (original["predio"], original["andar"], original["numero"]):
            refuse("Prédio, andar e número são fixos na planta da pousada.")
        current = self.db.execute("""SELECT MAX(quantidade) FROM reservas WHERE quarto_id=?
            AND (status='HOSPEDADA' OR (status='CONFIRMADA' AND saida>?))""",
            (record_id, clock.today().isoformat())).fetchone()[0]
        if current and (not dto.ativo or dto.status == "MANUTENCAO" or dto.capacidade < current):
            refuse("O quarto possui reservas ativas incompatíveis com esta alteração.")
        self.repo.update("quartos", record_id, dto.model_dump())
        self.repo.audit(self.user_id, "SALVAR", "quartos", record_id)
        return serialize_room(self.repo.get("quartos", record_id))

    def delete(self, entity, record_id):
        self.repo.get(entity, record_id)
        if entity == "quartos":
            refuse("Os 14 quartos fazem parte da planta fixa; use manutenção ou desative o quarto.")
        if entity != "hospedes":
            refuse("Exclusão não permitida para este cadastro.")
        if self.db.execute("SELECT 1 FROM reservas WHERE hospede_id=? AND status IN ('CONFIRMADA','HOSPEDADA')", (record_id,)).fetchone():
            refuse("Registro possui reservas ativas. Cancele ou finalize primeiro.")
        has_history = self.db.execute("SELECT 1 FROM reservas WHERE hospede_id=?", (record_id,)).fetchone()
        if has_history:
            self.repo.update(entity, record_id, {"ativo": 0})
        else:
            self.db.execute(f"DELETE FROM {entity} WHERE id=?", (record_id,))
        self.repo.audit(self.user_id, "DESATIVAR" if has_history else "EXCLUIR", entity, record_id)
        return {"mensagem": "Registro desativado; histórico preservado." if has_history else "Registro excluído."}


class ReservationService:
    def __init__(self, db, user_id):
        self.repo = Repository(db)
        self.db, self.user_id = db, user_id

    def quote(self, dto, record_id=None):
        original = self.repo.get("reservas", record_id) if record_id else None
        if original and original["status"] != "CONFIRMADA":
            refuse("Somente reservas confirmadas podem ser alteradas.")
        if dto.saida <= dto.entrada:
            refuse("Saída deve ser posterior à entrada (mínimo de uma diária).")
        if dto.entrada < clock.today() and (not original or str(dto.entrada) != original["entrada"]):
            refuse("Não é possível criar ou mover uma reserva para uma entrada no passado.")
        guest = self.repo.get("hospedes", dto.hospede_id)
        room = self.repo.get("quartos", dto.quarto_id)
        if not guest["ativo"]:
            refuse("Hóspede está inativo.")
        if not room["ativo"] or room["status"] == "MANUTENCAO":
            refuse("Quarto está inativo ou em manutenção.")
        count = 1 + len(dto.acompanhantes)
        if count > room["capacidade"]:
            refuse("Quantidade de hóspedes excede a capacidade do quarto.")
        if self.repo.conflicting(dto.quarto_id, dto.entrada, dto.saida, record_id or 0):
            refuse("Quarto indisponível: período conflitante ou hospedagem com saída atrasada.")
        daily = original["diaria_centavos"] if original and original["quarto_id"] == dto.quarto_id else room["diaria_centavos"]
        nights = (dto.saida - dto.entrada).days
        discount = cents(dto.desconto)
        if discount > daily * nights:
            refuse("Desconto não pode ultrapassar o valor das diárias.")
        total = daily * nights - discount
        if record_id and total < self.repo.paid(record_id):
            refuse("Novo total é menor que o valor pago. Registre os estornos necessários primeiro.")
        return {"diarias": nights, "quantidade": count, "diaria_centavos": daily, "desconto_centavos": discount, "total_centavos": total}

    def save(self, dto, record_id=None):
        quote = self.quote(dto, record_id)
        values = dto.model_dump(mode="json", exclude={"acompanhantes", "desconto"})
        values.update({key: value for key, value in quote.items() if key != "diarias"})
        if record_id:
            self.repo.update("reservas", record_id, values)
            self.db.execute("DELETE FROM acompanhantes WHERE reserva_id=?", (record_id,))
        else:
            values["codigo"] = "COL-" + uuid4().hex[:12].upper()
            record_id = self.repo.insert("reservas", values)
        for companion in dto.acompanhantes:
            self.repo.insert("acompanhantes", {"reserva_id": record_id, "nome": companion.nome})
        self.repo.audit(self.user_id, "SALVAR", "reservas", record_id)
        return reservation_details(self.repo, record_id)

    def transition(self, record_id, action):
        record = self.repo.get("reservas", record_id)
        command = COMMANDS[action](self, record)
        command.execute()
        self.repo.audit(self.user_id, action.upper(), "reservas", record_id)
        return reservation_details(self.repo, record_id)

    def pay(self, record_id, dto):
        record = self.repo.get("reservas", record_id)
        if record["status"] == "CANCELADA":
            refuse("Reserva cancelada não pode receber pagamentos.")
        amount = cents(dto.valor)
        if amount > record["total_centavos"] - self.repo.paid(record_id):
            refuse("Pagamento excede o saldo da reserva.")
        payment_id = self.repo.insert("pagamentos", {"reserva_id": record_id, "valor_centavos": amount, "forma": dto.forma, "usuario_id": self.user_id})
        self.repo.audit(self.user_id, "REGISTRAR", "pagamentos", payment_id)
        return serialize_payment(self.repo.get("pagamentos", payment_id))

    def refund(self, payment_id, dto):
        record = self.repo.get("pagamentos", payment_id)
        if record["status"] == "ESTORNADO":
            refuse("Este pagamento já foi estornado.")
        self.repo.update("pagamentos", payment_id, {"status": "ESTORNADO", "estornado_em": clock.now().isoformat(), "motivo_estorno": dto.motivo})
        self.repo.audit(self.user_id, "ESTORNAR", "pagamentos", payment_id)
        return serialize_payment(self.repo.get("pagamentos", payment_id))


class ReservationCommand:
    expected = "CONFIRMADA"
    target = ""

    def __init__(self, service, record):
        self.service, self.record = service, record

    def execute(self):
        if self.record["status"] != self.expected:
            refuse("Ação incompatível com o status atual da reserva.")
        changes = self.validate()
        self.service.repo.update("reservas", self.record["id"], {"status": self.target, **changes})


class CheckInCommand(ReservationCommand):
    target = "HOSPEDADA"

    def validate(self):
        if not self.record["entrada"] <= clock.today().isoformat() < self.record["saida"]:
            refuse("Check-in permitido apenas entre a entrada e o dia anterior à saída.")
        occupied = self.service.db.execute("SELECT 1 FROM reservas WHERE quarto_id=? AND status='HOSPEDADA'", (self.record["quarto_id"],)).fetchone()
        if occupied:
            refuse("Há outro hóspede no quarto. Registre o check-out antes.")
        return {"checkin_em": clock.now().isoformat()}


class CheckOutCommand(ReservationCommand):
    expected, target = "HOSPEDADA", "FINALIZADA"

    def validate(self):
        return {"checkout_em": clock.now().isoformat()}


class CancelCommand(ReservationCommand):
    target = "CANCELADA"

    def validate(self):
        if self.service.repo.paid(self.record["id"]):
            refuse("Confirme os estornos dos pagamentos antes de cancelar.")
        return {}


COMMANDS = {"check-in": CheckInCommand, "check-out": CheckOutCommand, "cancelar": CancelCommand}
