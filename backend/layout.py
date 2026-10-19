"""Planta fixa da pousada: um prédio, dois andares, sete quartos por andar."""

ROOMS = tuple((floor, floor * 100 + position) for floor in (1, 2) for position in range(1, 8))
DEFAULT_CAPACITY = 2
FIRST_FLOOR_DAILY_CENTS = 10_000
SECOND_FLOOR_EXTRA_CENTS = 2_000


def daily_cents(floor):
    return FIRST_FLOOR_DAILY_CENTS + (SECOND_FLOOR_EXTRA_CENTS if floor == 2 else 0)


def seed_rooms(connection):
    """Preenche somente um banco sem quartos; nunca altera inventário já usado."""
    if connection.execute("SELECT 1 FROM quartos LIMIT 1").fetchone():
        return
    connection.executemany("""INSERT INTO quartos
        (predio,andar,numero,capacidade,diaria_centavos,status,descricao)
        VALUES (1,?,?,?,?,'DISPONIVEL','Quarto cadastrado na planta inicial da pousada.')""",
        ((floor, number, DEFAULT_CAPACITY, daily_cents(floor)) for floor, number in ROOMS))


def enforce_floor_prices(connection):
    """Preço do inventário padrão: R$ 100 no 1º andar e R$ 120 no 2º."""
    connection.executemany(
        "UPDATE quartos SET diaria_centavos=? WHERE predio=1 AND andar=? AND numero=?",
        ((daily_cents(floor), floor, number) for floor, number in ROOMS),
    )
