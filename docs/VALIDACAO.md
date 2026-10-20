# Verificação da entrega — 19/10/2026

## Backend

Ambiente local: Windows, Python 3.13.7, FastAPI 0.143.3, Starlette 1.8.0, Pydantic 2.14.1 e tzdata 2025.2. Suite `tests/test_system.py`: **24 casos aprovados**, em 14,79 segundos na execução completa de 19/10/2026.

Cobertura dos cenários:

- Autenticação, cookie HttpOnly/SameSite, CSRF, logout e revogação por troca de senha.
- Limite de tentativas de login.
- CRUD de hóspede, endereço, CPF inválido/duplicado e mascaramento nas listas.
- Persistência de acompanhantes, cálculo exato em centavos e pagamentos parciais.
- Estados inválidos, check-in e check-out, pagamento após finalização.
- Sobreposição de períodos e limite de saída/entrada no mesmo dia.
- Datas no passado, diária zero, excesso de acompanhantes e descontos inválidos.
- Preservação da diária contratada e proteção de quartos com reservas.
- Cadastro automático e idempotente de 14 quartos: 101–107 e 201–207, sete por andar, com capacidade inicial de 2 pessoas, diária de R$ 100,00 no primeiro andar e R$ 120,00 no segundo.
- Migração transacional da estrutura antiga sem perda de quarto/reserva, remoção da tabela de categorias, preservação da diária contratada e integridade das chaves estrangeiras.
- Prédio, andar, número e diária fixos; criação/exclusão de quartos recusadas. Capacidade e condição continuam editáveis.
- Situação atual `LIVRE` com reserva confirmada, `OCUPADO` após check-in e novamente `LIVRE` após check-out; manutenção e inativação verificadas.
- Exemplo `manage.py demo` usa os quartos preexistentes, sem criar quartos extras.
- Estorno, cancelamento e preservação de histórico.
- Impedimento de reduzir total abaixo do valor já pago.
- Check-in futuro e hospedagem com saída atrasada.
- Virada do dia entre UTC e São Paulo: reserva/check-in ainda válidos no dia 1 local, chegadas/saídas no painel e bloqueio de hospedagem atrasada no dia 2 local.
- Duas reservas simultâneas: uma aprovada e uma recusada.
- Dois pagamentos simultâneos acima do saldo agregado: um aprovado e um recusado.
- Cabeçalhos de segurança, busca com conteúdo de injeção, OpenAPI e rejeição de total informado pelo cliente.
- Volume: **1.000 hóspedes + 1.000 reservas**, 30 consultas de hóspedes, reservas e dashboard; **p95 0,017 s**, **máximo 0,017 s**, abaixo do limite de 2 s no computador de teste. Isso mede execução local, sem latência de rede nem garantia de tempo em hospedagem externa.

Houve um aviso de depreciação da dependência Starlette sobre a compatibilidade do TestClient com httpx. Os testes passaram; o aviso não é erro da aplicação. Não foi ocultado.

### Atualização: primeiro acesso pela interface

A suíte completa passou novamente com **37 casos**. Os testes novos verificam código de ativação obrigatório, erro de código e de confirmação de senha, origem inválida, limite de tentativas, fechamento do cadastro após a primeira conta e concorrência entre duas tentativas simultâneas. O início no Render preserva o login antigo até `COLONIA_SETUP_CODE` ser configurado; com o código, não cria uma conta automática. `node --check frontend/app.js` passou.

Em Edge headless, com banco isolado e viewport de **360 px**, foram exercitados: formulário de primeiro acesso, rejeição de código inválido, criação da conta com código correto, logout e novo login. A captura local foi inspecionada; não houve rolagem horizontal nem erro JavaScript. O teste ocorreu localmente; a publicação no Render ainda precisa ser conferida no serviço.

### Atualização: modo de apresentação sem configuração de segredo

O `render.yaml` agora ativa `COLONIA_DEMO_MODE=1`, com código público `APRESENTACAO2026` exibido na página. A suíte completa passou com **39 casos**. Os testes adicionais verificam que o modo demo funciona sem configuração de segredo, prevalece sobre um código antigo, não cria automaticamente `edusilva`, aceita apenas a primeira conta e permite logout seguido de login. `node --check frontend/app.js` e `git diff --check` passaram.

No Edge headless, com banco isolado e viewport de **360 px**, o código de apresentação apareceu corretamente; cadastro, logout e login foram concluídos sem erros JavaScript ou rolagem horizontal. A captura da tela foi inspecionada. O serviço no Render ainda não foi verificado por este teste local. O código público não protege o primeiro cadastro: utilizar apenas dados fictícios.

### Atualização: login, cadastro e recuperação completos

A tela inicial voltou a mostrar sempre o login, agora com **Esqueci a senha** e **Não tenho cadastro**. O cadastro público é habilitado por `COLONIA_SELF_REGISTER=1` no Render e no `iniciar.bat`; o fluxo antigo de primeiro acesso fica indisponível nesse modo. Foi adicionada a tabela `codigos_recuperacao` sem alterar a tabela de usuários existente. O código individual é gerado aleatoriamente, guardado apenas como hash e apresentado uma vez; após redefinir a senha, as sessões antigas são revogadas e o código é substituído.

A suíte completa passou com **44 casos**. Os testes cobrem múltiplos cadastros, duplicidade, origem, login, logout, código inválido, limite de tentativas, confirmação de senha, revogação de sessão e geração de código para conta antiga. `node --check frontend/app.js` e `git diff --check` passaram. No Edge headless a **360 px**, foram verificados visualmente login inicial, cadastro, exibição do código, logout, recuperação e login com nova senha, sem erro JavaScript ou rolagem horizontal. A implantação no Render ainda não foi verificada neste teste local.

### Atualização: suporte ao PostgreSQL do Render

Com `DATABASE_URL`, a aplicação passa a usar PostgreSQL com esquema próprio, placeholders convertidos e retorno de IDs após inserção; sem a variável, mantém SQLite local. As gravações em PostgreSQL usam uma trava consultiva transacional global para preservar a serialização antes garantida por `BEGIN IMMEDIATE` no SQLite. O Blueprint declara um Render Postgres gratuito e injeta a URL interna no serviço web. A troca não importa automaticamente registros do banco antigo.

O driver `psycopg` 3.3.6 foi instalado no ambiente local de teste. A suíte completa passou com **49 casos** (44 existentes + 5 testes unitários da camada PostgreSQL), usando bancos SQLite temporários e um conector PostgreSQL simulado. O arquivo `schema_postgres.sql` foi analisado pelo parser PostgreSQL (`pglast`: 13 instruções válidas). **Não houve teste de integração contra um servidor PostgreSQL real nem publicação no Render**, pois não havia uma instância de banco disponível neste ambiente. Esses dois testes devem ser feitos após a sincronização do Blueprint.

### Correção após o primeiro deploy PostgreSQL

O log do Render mostrou `psycopg.errors.AmbiguousColumn` durante o cadastro: no UPSERT do contador de tentativas, `quantidade=quantidade+1` era ambíguo no PostgreSQL. As quatro ocorrências passaram a usar uma consulta única com `quantidade=tentativas_login.quantidade+1`, compatível também com SQLite. A suíte completa passou com **50 casos**; o teste adicional verifica duas inserções na mesma chave. O cadastro remoto precisa ser repetido após publicar esta correção.

## Navegador e apresentação

Fluxo real executado no Edge headless: login, simular disponibilidade, criar reserva com acompanhante, registrar pagamento, check-in, check-out, criar hóspede e consultar quartos disponíveis. Nenhum erro JavaScript capturado.

Chrome e Edge foram conferidos em **360 px** e **1440 px** com banco isolado após a mudança. O mapa mostrou 14 cartões em dois andares e R$ 120,00 no segundo; o menu/campo Categoria e a edição da diária não aparecem. A consulta de disponibilidade, a edição com número somente leitura, login, fechamento do diálogo com Escape, legibilidade do formulário no celular e ausência de erros JavaScript passaram. Tabelas extensas têm rolagem própria. `node --check frontend/app.js` e a compilação dos módulos Python passaram.

Os dados automatizados de teste ficaram em bancos separados sob `work/`. Antes da remoção das categorias, foi feito backup do banco local em `backups/colonia-before-category-removal-2026-10-19.sqlite3`. A migração foi testada em uma cópia e depois aplicada ao banco local, que já continha uma reserva `HOSPEDADA`: os 14 quartos e a reserva foram preservados, a tabela de categorias foi removida e `PRAGMA foreign_key_check` retornou vazio. O ZIP entregue exclui banco, backup e credenciais. Os arquivos do Sistema Colônia desktop não foram alterados.

## Limites desta verificação

- Dockerfile e roteiro de publicação estão incluídos; build Docker e hospedagem pública não foram executados.
- HTTPS, DNS, backup remoto e repositório online dependem da infraestrutura escolhida.
- Não houve auditoria WCAG completa, pentest ou teste de carga de produção.
- Não há processamento financeiro externo nem importação automática dos arquivos TXT antigos.
