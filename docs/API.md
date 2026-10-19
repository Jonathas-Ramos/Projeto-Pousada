# Contrato da API

Base: `/api`. JSON UTF-8. Datas `YYYY-MM-DD`. Reais em números/strings decimais com até duas casas na entrada. Valores internos em centavos; respostas monetárias em reais. "Hoje" e os limites de check-in são avaliados em `America/Sao_Paulo`, independentemente do fuso do servidor.

O login gera cookie HttpOnly e retorna `{id, nome, csrf}`. Todas as operações protegidas exigem cookie válido. POST/PUT/PATCH/DELETE protegidos exigem `X-CSRF-Token` igual ao `csrf` da sessão. Não há CORS aberto. Cadastro e recuperação conferem a origem quando o navegador a envia.

| Recurso | Operações |
|---|---|
| `/auth/registration` | GET `{enabled}` para mostrar ou ocultar a opção de cadastro |
| `/auth/register` | POST `{nome, login, senha, confirmar_senha}` cria conta se `COLONIA_SELF_REGISTER=1`; retorna `recovery_code` uma única vez |
| `/auth/reset-password` | POST `{login, codigo, nova_senha, confirmar_senha}` troca senha, revoga sessões e retorna um novo `recovery_code` |
| `/auth/recovery-code` | POST autenticado `{senha_atual}` gera/substitui o código de recuperação; exige CSRF |
| `/auth/first-access` | Fluxo antigo preservado para instalações fechadas; indisponível quando `COLONIA_SELF_REGISTER=1` |
| `/auth/login` | POST `{login, senha}` |
| `/auth/me` | GET identidade e token CSRF |
| `/auth/logout` | POST revogar sessão |
| `/auth/senha` | PUT `{senha_atual, nova_senha}` e revogar todas as sessões |
| `/hospedes` | GET com `q, limit, offset`; POST |
| `/hospedes/{id}` | GET, PUT, DELETE (excluir/desativar conforme histórico) |
| `/quartos` | GET; POST retorna `409` (planta fixa) |
| `/quartos/{id}` | GET, PUT; DELETE retorna `409` (planta fixa) |
| `/quartos/disponiveis` | GET `entrada, saida, pessoas` |
| `/reservas` | GET `q, status, limit, offset`; POST |
| `/reservas/{id}` | GET, PUT, DELETE (cancelamento lógico) |
| `/reservas/simular` | POST; `reserva_id` opcional para simular edição |
| `/reservas/{id}/check-in` | PATCH |
| `/reservas/{id}/check-out` | PATCH |
| `/reservas/{id}/cancelar` | PATCH |
| `/reservas/{id}/pagamentos` | POST `{valor, forma}` |
| `/pagamentos/{id}/estornar` | POST `{motivo, confirmado:true}` |
| `/dashboard` | GET indicadores e chegadas/saídas |
| `/auditoria` | GET; `limit` opcional |
| `/openapi.json` | GET especificação OpenAPI autenticada |
| `/health` | GET público; sem dados pessoais |

As listas de hóspedes e reservas retornam `{items: [...], total: N}`, com 50 itens por padrão e limite máximo de 200. Consultas por ID retornam um objeto. Quartos retornam a lista da planta fixa. As rotas `/categorias` foram removidas.

Os 14 quartos são criados ao inicializar um banco sem quartos: 101–107 no 1º andar a R$ 100,00/noite e 201–207 no 2º a R$ 120,00/noite. A resposta de `GET /quartos` e `GET /quartos/{id}` inclui `situacao_atual`: `LIVRE`, `OCUPADO`, `MANUTENCAO` ou `INATIVO`. A ocupação é derivada de uma reserva com check-in realizado e check-out pendente; para uma data futura, use `/quartos/disponiveis`. `PUT /quartos/{id}` permite editar capacidade e condição, mas não prédio, andar, número ou diária. POST e DELETE de quartos retornam `409`. Reservas ativas ainda restringem manutenção, inativação e redução de capacidade.

## Criar reserva

```json
{
  "hospede_id": 1,
  "quarto_id": 2,
  "entrada": "2026-12-01",
  "saida": "2026-12-03",
  "acompanhantes": [{"nome": "Acompanhante Exemplo"}],
  "desconto": "10.00",
  "observacoes": "Chegada prevista no período da tarde"
}
```

As datas são ilustrativas; use datas presentes/futuras. A resposta inclui `id`, código, datas, quantidade derivada, `valor_diaria`, `valor_total`, desconto, status, acompanhantes, pagamentos, `valor_pago` e `saldo`. Não se aceita `valor_total`, `status` nem quantidade arbitrária na entrada.

## Respostas e erros

- `200`: consulta, edição ou ação concluída.
- `201`: registro criado.
- `400`: credencial/código de recuperação incorreto, confirmação de senha diferente ou requisição inválida.
- `401`: login inválido ou sessão ausente/expirada.
- `403`: CSRF/origem inválidos ou cadastro público desativado.
- `404`: registro não encontrado.
- `409`: usuário já ocupado, CPF duplicado, tentativa de alterar a planta fixa, conflito de reserva ou outra regra de negócio.
- `410`: rota antiga de primeiro acesso desativada quando o cadastro público está habilitado.
- `413`: corpo declarado maior que o limite da aplicação.
- `422`: erro de tipo/formato; corpo contém `detail` e `campos` com nome e mensagem, sem ecoar entradas sensíveis.
- `429`: tentativas de login, recuperação ou cadastro excedidas; janela de 15 minutos.
- `503`: banco temporariamente indisponível ou primeiro acesso sem código configurado.

Exemplo: `{"detail":"Quantidade de hóspedes excede a capacidade do quarto."}`.
