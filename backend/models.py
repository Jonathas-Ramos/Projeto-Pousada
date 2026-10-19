"""DTOs tipados: validação compartilhada por API, documentação e serviços."""
import re
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import clock


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Endereco(DTO):
    cep: str = Field(min_length=8, max_length=9)
    logradouro: str = Field(min_length=2, max_length=150)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str = Field(default="", max_length=100)
    bairro: str = Field(min_length=2, max_length=100)
    cidade: str = Field(min_length=2, max_length=100)
    estado: str = Field(pattern=r"^[A-Za-z]{2}$")
    pais: str = Field(default="Brasil", min_length=2, max_length=60)

    @field_validator("cep")
    @classmethod
    def validar_cep(cls, value):
        value = re.sub(r"[\s-]", "", value)
        if not re.fullmatch(r"[0-9]{8}", value):
            raise ValueError("CEP deve conter 8 dígitos.")
        return value

    @field_validator("estado")
    @classmethod
    def uppercase(cls, value):
        return value.upper()


def cpf_valido(value):
    if not re.fullmatch(r"[0-9]{11}", value) or len(set(value)) == 1:
        return False
    for n in (9, 10):
        digito = (sum(int(value[i]) * (n + 1 - i) for i in range(n)) * 10) % 11
        if int(value[n]) != (0 if digito == 10 else digito):
            return False
    return True


class Hospede(DTO):
    nome: str = Field(min_length=3, max_length=150)
    cpf: str = Field(max_length=18)
    nascimento: date
    email: str = Field(min_length=5, max_length=200)
    telefone: str = Field(min_length=8, max_length=25)
    genero: str = Field(default="", max_length=40)
    nacionalidade: str = Field(default="Brasileira", min_length=2, max_length=60)
    observacoes: str = Field(default="", max_length=1000)
    ativo: bool = True
    endereco: Endereco

    @field_validator("cpf")
    @classmethod
    def cpf_check(cls, value):
        value = re.sub(r"[.\s-]", "", value)
        if not cpf_valido(value):
            raise ValueError("CPF inválido.")
        return value

    @field_validator("nascimento")
    @classmethod
    def birth_check(cls, value):
        if not date(1900, 1, 1) <= value <= clock.today():
            raise ValueError("Data de nascimento inválida.")
        return value

    @field_validator("email")
    @classmethod
    def email_check(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido.")
        return value.lower()


class Quarto(DTO):
    numero: int = Field(gt=0, le=9999)
    predio: int = Field(gt=0, le=999)
    andar: int = Field(default=0, ge=-5, le=100)
    capacidade: int = Field(ge=1, le=30)
    status: Literal["DISPONIVEL", "MANUTENCAO"] = "DISPONIVEL"
    descricao: str = Field(default="", max_length=1000)
    acessivel: bool = False
    ativo: bool = True


class Acompanhante(DTO):
    nome: str = Field(min_length=3, max_length=150)


class Reserva(DTO):
    hospede_id: int = Field(gt=0)
    quarto_id: int = Field(gt=0)
    entrada: date
    saida: date
    acompanhantes: list[Acompanhante] = Field(default_factory=list, max_length=29)
    desconto: Decimal = Field(default=Decimal("0.00"), ge=0, le=10000000, decimal_places=2)
    observacoes: str = Field(default="", max_length=1000)


class Pagamento(DTO):
    valor: Decimal = Field(gt=0, le=10000000, decimal_places=2)
    forma: Literal["PIX", "DINHEIRO", "CARTAO", "TRANSFERENCIA"]


class Estorno(DTO):
    motivo: str = Field(min_length=5, max_length=300)
    confirmado: Literal[True]


class Login(DTO):
    login: str = Field(min_length=1, max_length=100)
    senha: str = Field(min_length=1, max_length=200)


class PrimeiroAcesso(DTO):
    nome: str = Field(min_length=3, max_length=150)
    login: str = Field(pattern=r"^[A-Za-z0-9._-]{3,100}$")
    senha: str = Field(min_length=12, max_length=200)
    confirmar_senha: str = Field(min_length=12, max_length=200)
    codigo: str = Field(min_length=1, max_length=200)


class TrocaSenha(DTO):
    senha_atual: str = Field(min_length=1, max_length=200)
    nova_senha: str = Field(min_length=12, max_length=200)
