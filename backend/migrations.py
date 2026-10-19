"""Migração transacional da versão que usava categoria nos quartos."""


def remove_categories(connection):
    columns = {row[1] for row in connection.execute("PRAGMA table_info(quartos)")}
    if "categoria_id" in columns:
        connection.execute("""CREATE TABLE quartos_sem_categoria (
            id INTEGER PRIMARY KEY, numero INTEGER NOT NULL CHECK(numero>0),
            predio INTEGER NOT NULL CHECK(predio>0), andar INTEGER NOT NULL DEFAULT 0,
            capacidade INTEGER NOT NULL CHECK(capacidade BETWEEN 1 AND 30),
            diaria_centavos INTEGER NOT NULL CHECK(diaria_centavos>0),
            status TEXT NOT NULL DEFAULT 'DISPONIVEL' CHECK(status IN ('DISPONIVEL','MANUTENCAO')),
            descricao TEXT NOT NULL DEFAULT '', acessivel INTEGER NOT NULL DEFAULT 0 CHECK(acessivel IN (0,1)),
            ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1)), UNIQUE(predio,numero)
        )""")
        connection.execute("""INSERT INTO quartos_sem_categoria
            (id,numero,predio,andar,capacidade,diaria_centavos,status,descricao,acessivel,ativo)
            SELECT id,numero,predio,andar,capacidade,diaria_centavos,status,descricao,acessivel,ativo
            FROM quartos""")
        connection.execute("DROP TABLE quartos")
        connection.execute("ALTER TABLE quartos_sem_categoria RENAME TO quartos")
    connection.execute("DROP TABLE IF EXISTS categorias")
