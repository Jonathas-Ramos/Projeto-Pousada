# Diagramas do ColôniaWeb

## Entidades e relacionamentos

```mermaid
erDiagram
    HOSPEDE ||--|| ENDERECO : possui
    HOSPEDE ||--o{ RESERVA : titular
    QUARTO ||--o{ RESERVA : recebe
    RESERVA ||--o{ ACOMPANHANTE : inclui
    RESERVA ||--o{ PAGAMENTO : recebe
    USUARIO ||--o{ PAGAMENTO : registra
    USUARIO ||--o{ SESSAO : autentica
    HOSPEDE {
        int id PK
        string nome
        string cpf UK
        date nascimento
        string email
        string telefone
        string genero
        string nacionalidade
        string observacoes
        bool ativo
        datetime criado_em
    }
    ENDERECO {
        int id PK
        int hospede_id FK,UK
        string cep
        string logradouro
        string numero
        string complemento
        string bairro
        string cidade
        string estado
        string pais
    }
    QUARTO {
        int id PK
        int numero
        int predio
        int andar
        int capacidade
        int diaria_centavos
        string status
        string descricao
        bool acessivel
        bool ativo
    }
    RESERVA {
        int id PK
        string codigo UK
        int hospede_id FK
        int quarto_id FK
        date entrada
        date saida
        int quantidade
        int diaria_centavos
        int desconto_centavos
        int total_centavos
        string status
        string observacoes
        datetime criado_em
        datetime checkin_em
        datetime checkout_em
    }
    ACOMPANHANTE {
        int id PK
        int reserva_id FK
        string nome
    }
    PAGAMENTO {
        int id PK
        int reserva_id FK
        int usuario_id FK
        int valor_centavos
        string forma
        string status
        datetime registrado_em
        datetime estornado_em
        string motivo_estorno
    }
    USUARIO {
        int id PK
        string nome
        string login UK
        string senha_hash
        bool ativo
    }
    SESSAO {
        string token_hash PK
        int usuario_id FK
        string csrf
        int expira
    }
```

Os 11 atributos de Hóspede, 10 de Quarto e 15 de Reserva são persistidos. `quantidade` é calculada a partir do titular e dos acompanhantes. `ENDERECO.hospede_id` é único; a criação de hóspede/endereço é atômica. Registros de endereço representam o endereço individual do cadastro, mesmo quando duas pessoas informam o mesmo logradouro.

Na implantação atual, `layout.py` cadastra automaticamente 14 quartos no prédio 1, com `andar/numero` 1/101–107 e 2/201–207. A diária é R$ 100 no 1º andar e R$ 120 no 2º. Não existe entidade Categoria. A planta é fixa na API; `situacao_atual` não é uma coluna persistida, mas um valor derivado de `ativo`, `status` e reservas `HOSPEDADA`.

## Classes de domínio e implementação

Os DTOs Pydantic representam entradas de domínio; a persistência usa linhas SQLite via DAO, sem entidades ORM ocultas.

```mermaid
classDiagram
    class Hospede {
        +str nome
        +str cpf
        +date nascimento
        +str email
        +str telefone
        +str genero
        +str nacionalidade
        +str observacoes
        +bool ativo
        +Endereco endereco
        +cpf_check(value)
    }
    class Endereco {
        +str cep
        +str logradouro
        +str numero
        +str complemento
        +str bairro
        +str cidade
        +str estado
        +str pais
    }
    class Quarto {
        +int numero
        +int predio
        +int andar
        +int capacidade
        +str status
        +bool ativo
    }
    class Reserva {
        +int hospede_id
        +int quarto_id
        +date entrada
        +date saida
        +list acompanhantes
        +Decimal desconto
        +str observacoes
    }
    class Acompanhante {
        +str nome
    }
    class CatalogService {
        +save_guest(dto, id)
        +save_room(dto, id)
        +delete(entity, id)
    }
    class ReservationService {
        +quote(dto, id)
        +save(dto, id)
        +transition(id, action)
        +pay(id, dto)
        +refund(id, dto)
    }
    class Repository {
        +get(table, id)
        +insert(table, values)
        +update(table, id, values)
        +conflicting(room, start, end, ignore)
        +paid(reservation_id)
        +audit(user, action, entity, id)
    }
    class ReservationCommand {
        +execute()
        +validate()
    }
    class CheckInCommand {
        +validate()
    }
    class CheckOutCommand {
        +validate()
    }
    class CancelCommand {
        +validate()
    }
    Hospede "1" *-- "1" Endereco
    Reserva "1" *-- "0..*" Acompanhante
    CatalogService ..> Hospede
    CatalogService ..> Quarto
    CatalogService --> Repository
    ReservationService ..> Reserva
    ReservationService --> Repository
    ReservationService --> ReservationCommand
    ReservationCommand <|-- CheckInCommand
    ReservationCommand <|-- CheckOutCommand
    ReservationCommand <|-- CancelCommand
```

## Sequência: confirmar reserva

```mermaid
sequenceDiagram
    actor Recepcao
    participant Frontend
    participant API as Controller FastAPI
    participant Auth as Segurança
    participant Service as ReservationService
    participant DAO as Repository
    participant DB as SQLite
    Recepcao->>Frontend: Preenche titular, quarto, datas e acompanhantes
    Frontend->>API: POST /api/reservas + cookie + CSRF
    API->>Auth: Validar sessão e CSRF
    Auth-->>API: Usuário autenticado
    API->>API: Validar DTO
    API->>DB: BEGIN IMMEDIATE
    API->>Service: save(dto)
    Service->>DAO: Consultar hóspede, quarto e conflitos
    DAO->>DB: SELECT parametrizado
    DB-->>DAO: Registros e disponibilidade
    DAO-->>Service: Resultado
    alt Capacidade, período ou disponibilidade inválidos
        Service-->>API: Erro de regra de negócio
        API->>DB: ROLLBACK
        API-->>Frontend: 409 + mensagem
        Frontend-->>Recepcao: Explicar impedimento
    else Reserva válida
        Service->>Service: Calcular total em centavos
        Service->>DAO: Inserir reserva, acompanhantes e auditoria
        DAO->>DB: INSERT parametrizado
        Service-->>API: Reserva calculada
        API->>DB: COMMIT
        API-->>Frontend: 201 + reserva
        Frontend-->>Recepcao: Confirmação
    end
```

## Sequência: check-in / check-out / cancelamento

```mermaid
sequenceDiagram
    actor Recepcao
    participant UI as Frontend
    participant API
    participant Service as ReservationService
    participant Command as Comando selecionado
    participant DB as SQLite
    Recepcao->>UI: Escolhe ação e confirma
    UI->>API: PATCH /api/reservas/id/ação
    API->>API: Autenticação + CSRF
    API->>DB: BEGIN IMMEDIATE
    API->>Service: transition(id, ação)
    Service->>Command: execute()
    Command->>Command: Validar estado, datas e impedimentos
    Command->>DB: Atualizar status e momento real
    Service->>DB: Registrar auditoria
    API->>DB: COMMIT
    API-->>UI: Reserva atualizada
```

## Sequência: primeiro acesso

```mermaid
sequenceDiagram
    actor Responsavel
    participant UI as Página de login
    participant API as FastAPI
    participant DB as SQLite
    Responsavel->>UI: Abre o sistema
    UI->>API: GET /api/auth/first-access
    API->>DB: Verificar se existe usuário
    DB-->>API: Banco sem usuários
    API-->>UI: Exibir formulário inicial
    Responsavel->>UI: Nome, usuário, senha e código exibido (demonstração)
    UI->>API: POST /api/auth/first-access
    API->>API: Validar origem, senha e código do modo ativo
    API->>DB: BEGIN IMMEDIATE + verificar ausência de usuário
    API->>DB: Inserir primeiro usuário, auditoria e sessão
    API->>DB: COMMIT
    API-->>UI: Cookie de sessão e usuário autenticado
    Note over API,DB: Novas tentativas de primeiro acesso retornam 409
```
