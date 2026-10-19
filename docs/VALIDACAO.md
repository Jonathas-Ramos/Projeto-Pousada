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

## Navegador e apresentação

Fluxo real executado no Edge headless: login, simular disponibilidade, criar reserva com acompanhante, registrar pagamento, check-in, check-out, criar hóspede e consultar quartos disponíveis. Nenhum erro JavaScript capturado.

Chrome e Edge foram conferidos em **360 px** e **1440 px** com banco isolado após a mudança. O mapa mostrou 14 cartões em dois andares e R$ 120,00 no segundo; o menu/campo Categoria e a edição da diária não aparecem. A consulta de disponibilidade, a edição com número somente leitura, login, fechamento do diálogo com Escape, legibilidade do formulário no celular e ausência de erros JavaScript passaram. Tabelas extensas têm rolagem própria. `node --check frontend/app.js` e a compilação dos módulos Python passaram.

Os dados automatizados de teste ficaram em bancos separados sob `work/`. Antes da remoção das categorias, foi feito backup do banco local em `backups/colonia-before-category-removal-2026-10-19.sqlite3`. A migração foi testada em uma cópia e depois aplicada ao banco local, que já continha uma reserva `HOSPEDADA`: os 14 quartos e a reserva foram preservados, a tabela de categorias foi removida e `PRAGMA foreign_key_check` retornou vazio. O ZIP entregue exclui banco, backup e credenciais. Os arquivos do Sistema Colônia desktop não foram alterados.

## Limites desta verificação

- Dockerfile e roteiro de publicação estão incluídos; build Docker e hospedagem pública não foram executados.
- HTTPS, DNS, backup remoto e repositório online dependem da infraestrutura escolhida.
- Não houve auditoria WCAG completa, pentest ou teste de carga de produção.
- Não há processamento financeiro externo nem importação automática dos arquivos TXT antigos.
