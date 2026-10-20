# ColôniaWeb

Sistema web de gestão de hospedagens, adaptado do conceito do Sistema Colônia em Python/Tkinter para a avaliação M1 de Aplicativos para Web. Backend em Python/FastAPI, frontend independente em HTML/CSS/JavaScript e banco relacional SQLite local ou PostgreSQL no Render. Não contém serviços adicionais nem processamento bancário.

## Começar no Windows

1. Tenha **Python 3.13** instalado e disponível no comando `python`.
2. Execute **`iniciar.bat`**. Na primeira execução, é necessário acesso à internet para instalar as dependências em `.venv`.
3. Acesse **http://127.0.0.1:8000**. A tela inicial mostra usuário, senha, **Esqueci a senha** e **Não tenho cadastro**.
4. Em **Não tenho cadastro**, informe nome, usuário e senha de pelo menos 12 caracteres. Guarde o código de recuperação mostrado uma única vez; depois, entre com seu novo usuário e senha. Não há senha padrão.
5. Os 14 quartos já aparecem em **Quartos e mapa**. Cadastre um hóspede e crie sua primeira reserva. A diária é R$ 100,00 no 1º andar e R$ 120,00 no 2º.

Mantenha a janela do servidor aberta enquanto usa o sistema. `Ctrl+C` encerra o servidor. Sem `DATABASE_URL`, os dados permanecem em `data/colonia.sqlite3`.

### Exemplos para apresentação

Após criar o usuário, em outro terminal na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe manage.py demo
```

Cria dois hóspedes fictícios e duas reservas relativas à data da execução, usando os quartos 101 e 201 já cadastrados. Só funciona sem hóspedes/reservas e não sobrescreve dados. Os CPFs de exemplo passam na validação matemática, mas o sistema não verifica se correspondem a pessoas reais.

### Execução manual / Linux / macOS

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
export COLONIA_SELF_REGISTER=1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

No Windows, também é possível usar diretamente `.venv\Scripts\python.exe` sem ativar o ambiente. Se iniciar manualmente pelo PowerShell, defina `$env:COLONIA_SELF_REGISTER='1'` antes do comando do servidor; `iniciar.bat` já faz isso.

## Funcionalidades

- Tela de login como entrada principal; cadastro de usuários pela opção **Não tenho cadastro**, login, logout, recuperação de senha com código individual e troca de senha autenticada.
- CRUD de hóspedes, endereço individual e reservas; consulta e edição de capacidade/condição dos quartos da planta fixa.
- Pesquisa de hóspedes por nome/CPF, listagem paginada e consulta por ID.
- CPF validado, normalizado e único. Listas exibem CPF mascarado.
- 14 quartos preexistentes em um prédio: 101–107 no 1º andar por R$ 100,00/noite e 201–207 no 2º por R$ 120,00/noite. O mapa mostra **Livre**, **Ocupado**, **Manutenção** ou **Inativo**; disponibilidade futura pesquisável por período e quantidade.
- Reservas com responsável, acompanhantes salvos individualmente, datas e desconto.
- Simulação e cálculo obrigatório do total no backend, sem confiar no preço enviado pelo navegador.
- Validação de conflitos de datas, capacidade, quarto ativo e manutenção.
- Check-in, check-out, cancelamento e histórico preservado.
- Pagamentos parciais, controle de saldo e confirmação de estornos externos.
- Dashboard com chegadas, saídas, ocupação, hóspedes e recebimentos acumulados.
- Auditoria por ID do registro, sem CPF/endereço/senha nos eventos.
- Swagger/OpenAPI protegido, testes automatizados e Dockerfile.

## Regras consolidadas

1. Uma reserva contém um responsável e zero ou mais acompanhantes; a capacidade inclui todos.
2. Cada hóspede tem um registro individual de endereço. O vínculo 1:1 é garantido por FK com `UNIQUE`; ambos são gravados em uma transação.
3. A pousada possui uma planta fixa de 14 quartos no prédio 1: sete no 1º andar (101–107) e sete no 2º (201–207). Eles são criados automaticamente quando o banco ainda não tem quartos; bancos que já contêm quartos são preservados, sem renumeração automática. Não é permitido criar, excluir ou renumerar quartos pela API. Capacidade, acessibilidade e manutenção são editáveis. A categoria foi removida. A capacidade inicial é **2 pessoas**.
4. **Ocupado** significa check-in realizado e check-out ainda não realizado. Sem hospedagem em andamento, o quarto aparece **Livre**, salvo se estiver em manutenção ou inativo. Uma reserva apenas confirmada não ocupa o quarto agora, mas bloqueia suas datas na consulta de disponibilidade. A situação é calculada das reservas; não é alterada manualmente.
5. Datas usam o intervalo `[entrada, saída)`: a saída não é uma diária e pode coincidir com a entrada da próxima reserva.
6. Reservas confirmadas e hospedadas bloqueiam períodos sobrepostos. Hospedagens com saída atrasada bloqueiam novas reservas até o check-out.
7. Não é permitido criar entrada no passado. Uma reserva já confirmada pode conservar sua data original durante outras alterações.
8. `total = (saída - entrada em dias) × diária contratada - desconto`.
9. A diária é fixa por andar: **R$ 100,00** no 1º e **R$ 120,00** no 2º. Não há campo para alterá-la na interface/API. A diária contratada é copiada para a reserva; alterações futuras do código de preços não reprecificam reservas existentes. Editar uma reserva para outro quarto usa a diária do novo andar.
10. Dinheiro é armazenado em centavos inteiros. Desconto deve estar entre zero e o subtotal.
11. Fluxos: `CONFIRMADA → HOSPEDADA → FINALIZADA` ou `CONFIRMADA → CANCELADA`. Somente confirmadas são editáveis.
12. Check-in: entre a entrada, inclusive, e a saída, exclusive; exige ausência de outra hospedagem em andamento no quarto.
13. Check-out registra o momento real e libera a ocupação. Saída antecipada ou atrasada não altera automaticamente o preço contratado nesta versão.
14. Pagamentos são registros de valores recebidos externamente, inclusive após a finalização, e nunca podem superar o saldo. Reservas canceladas não recebem pagamentos.
15. Antes de cancelar uma reserva paga, a recepção deve realizar a devolução externamente e confirmar o estorno no sistema, com motivo. O sistema não movimenta dinheiro.
16. Hóspedes com reservas ativas não podem ser excluídos. Com histórico, a exclusão desativa; sem histórico, exclui. Quartos da planta fixa nunca são excluídos; podem ser desativados quando não houver reserva ativa. A exclusão de reserva é cancelamento lógico. Pagamentos não são apagados.
17. Quarto com reservas ativas não pode ser desativado, colocado em manutenção ou ter capacidade reduzida abaixo da quantidade reservada.
18. Todos os critérios de "hoje" (reserva, disponibilidade, check-in, atrasos e painel) usam explicitamente o calendário `America/Sao_Paulo`, independentemente do fuso do servidor. Instantes de check-in, check-out e estorno são gravados com o deslocamento da região (atualmente `-03:00`); carimbos automáticos do banco permanecem em UTC.
19. Os registros de serviço, preço de serviços e tabelas associativas de serviços foram removidos do escopo.

## Organização e padrões

```text
backend/
  main.py        Rotas/controllers HTTP, proteção e documentação
  models.py      DTOs e validações de entrada (Pydantic)
  services.py    Regras de negócio e comandos de estado
  repository.py DAO, consultas e serialização
  database.py   Factory de conexões e unidade de trabalho
  clock.py      Calendário operacional de São Paulo
  layout.py     Planta fixa e cadastro inicial dos 14 quartos
  migrations.py Migração da versão anterior que possuía categoria
  schema.sql    Entidades, chaves e restrições
  security.py   Autenticação, sessão, CSRF e proteção de senhas
frontend/
  index.html    Estrutura e login
  app.js        Cliente da API, navegação e views
  styles.css    Interface responsiva
tests/          Integração, regras, concorrência e desempenho
docs/           Diagramas, API, segurança e matriz da M1
manage.py       Usuários, exemplos e backup
```

Padrões efetivamente usados: **DAO/Repository**, **Command** para check-in/check-out/cancelamento, **Factory de conexões** e **Unit of Work** para transações. Há separação entre apresentação, controllers, domínio e persistência, compatível com uma organização MVC de aplicação web. A função factory de conexões não é apresentada como implementação completa do padrão GoF Factory Method. Não foram acrescentados Builder ou Decorator artificialmente; confirme com o professor quais padrões ele exige.

Backend e frontend são separados no código e se comunicam por HTTP/JSON. Por simplicidade de execução, a API também entrega os arquivos estáticos sob a mesma origem, sem necessidade de CORS. Isso não é um frontend Tkinter nem acesso direto do navegador ao banco.

## Documentação e testes

Após entrar, acesse `/docs` pelo menu. Para executar escritas pelo Swagger, consulte `GET /api/auth/me` e copie o campo `csrf` para o parâmetro **X-CSRF-Token**; o cookie HttpOnly já é enviado pelo navegador. A interface normal faz isso automaticamente. Swagger carrega recursos de `cdn.jsdelivr.net`; as demais telas funcionam sem CDN.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q -s
```

Os testes usam bancos temporários e não alteram a base real. Os diagramas de classes, relacionamentos e sequência estão em [docs/DIAGRAMAS.md](docs/DIAGRAMAS.md). Veja [docs/API.md](docs/API.md), [docs/SEGURANCA.md](docs/SEGURANCA.md), [docs/M1.md](docs/M1.md) e [docs/VALIDACAO.md](docs/VALIDACAO.md).

A dependência `tzdata` fornece a base de fusos no Windows; sem ela, `zoneinfo` não encontra `America/Sao_Paulo`. A primeira execução continua exigindo internet para instalar as dependências.

## Backup

```sh
python manage.py backup backups/colonia-2026-10-18.sqlite3
```

O comando usa o mecanismo de backup do SQLite e recusa sobrescrever um destino existente. Guarde backups fora de repositórios públicos. Para restaurar, pare todos os processos do servidor e configure `COLONIA_DB` para apontar para uma cópia recuperada do backup; mantenha a base anterior como recuperação. Não copie somente o arquivo principal enquanto houver uma gravação em modo WAL.

Com `DATABASE_URL` configurada, o comando acima não se aplica. Para PostgreSQL, use as ferramentas `pg_dump`/`pg_restore` com a URL **externa** do banco, sem colocar credenciais no repositório.

## Publicação

O Dockerfile prepara a execução, mas a hospedagem pública e o envio para um repositório remoto ainda precisam ser feitos na conta escolhida por você. Nenhum recurso pago ou conta externa foi criado.

```sh
docker build -t coloniaweb .
docker volume create colonia-data
docker run -d --name coloniaweb -p 127.0.0.1:8000:8000 -v colonia-data:/data -e COLONIA_HOSTS=localhost,127.0.0.1,seu-dominio.example -e COLONIA_SECURE_COOKIE=1 coloniaweb
docker exec -it coloniaweb python manage.py admin
```

Em produção em servidor próprio, coloque um proxy reverso com **HTTPS** à frente do container, configure o hostname real em `COLONIA_HOSTS` e `COLONIA_SECURE_COOKIE=1`. Configure os cabeçalhos `Host` e `X-Forwarded-Proto` do proxy e permita somente o IP do proxy em `--forwarded-allow-ips` do Uvicorn. Não use `*` para proxies não confiáveis. Os exemplos do `.env.example` são variáveis de ambiente; o arquivo não é carregado automaticamente. No Render, siga a configuração específica abaixo.

Para **preservar** dados no SQLite, use volume persistente, uma única instância da aplicação e backups. Uma hospedagem com disco efêmero perderá os dados ao recriar a instância. Com PostgreSQL, o projeto usa uma transação e trava consultiva global nas operações de escrita para manter atômica a verificação de conflitos. Docker/HTTPS remoto e PostgreSQL real não foram executados neste ambiente.

### Render com PostgreSQL gerenciado

O `render.yaml` agora declara um serviço web e um banco `coloniaweb-db` no plano gratuito. O Render injeta a URL **interna** do Postgres em `DATABASE_URL`; ela nunca deve ser copiada para o GitHub. Quando `DATABASE_URL` está presente, o programa cria as tabelas e os 14 quartos no PostgreSQL. Sem ela, continua usando SQLite local.

1. Envie os arquivos atualizados, inclusive `backend/schema_postgres.sql`, `requirements.txt` e `render.yaml`, para a raiz do repositório. Não envie `.env`, `data/`, `.venv/` nem `backups/`.
2. No Render, abra o Blueprint ligado ao repositório e sincronize o `render.yaml`. Confirme que o banco `coloniaweb-db` e o serviço `coloniaweb` estão na **mesma região**. Se o web service tiver sido criado manualmente, crie um Render Postgres separadamente, copie a **Internal Database URL** em **Environment → DATABASE_URL** do serviço e faça novo deploy; nesse caso, não crie outro banco pelo Blueprint.
3. Espere o deploy finalizar, abra `/api/health`, cadastre um usuário e confira **Quartos e mapa** (14 quartos). Faça um cadastro de hóspede e uma reserva fictícia; saia e entre novamente para verificar que os dados continuam após um novo deploy.

**Atenção:** trocar o banco não transfere contas, reservas ou hóspedes do SQLite antigo. O PostgreSQL começará vazio, com apenas os 14 quartos iniciais. Guarde um backup do SQLite antes da troca. A migração de registros antigos exige uma importação separada. Se `DATABASE_URL` estiver incorreta ou o banco estiver indisponível, o serviço falha; ele **não** volta silenciosamente ao SQLite.

O [Postgres gratuito do Render](https://render.com/docs/free) expira **30 dias** após a criação, tem limite de 1 GB e não oferece backups gerenciados. Após expirar, há prazo de 14 dias para mudar para um plano pago; depois os dados podem ser excluídos. Planeje isso antes da apresentação. A URL interna do banco só funciona entre serviços na mesma conta/região.

### Render antigo: demonstração acadêmica descartável com SQLite

Se você **não** configurar `DATABASE_URL`, ainda é possível publicar só o serviço web com SQLite, sem VPS e sem migrar o banco. **Os dados cadastrados no Render podem desaparecer** quando a instância gratuita reinicia ou é atualizada; a cópia local continua sendo a principal. Use apenas dados fictícios. O plano gratuito não fornece disco persistente para SQLite. Consulte os [limites atuais do Render](https://render.com/docs/free) antes de publicar.

1. Coloque **o conteúdo desta pasta `ColoniaWeb` na raiz de um repositório Git**, sem `data/`, `backups/`, `.venv/` ou `.env`. O arquivo `render.yaml` deve ficar na raiz do repositório. Pode ser privado, desde que você autorize o Render a acessá-lo.
2. Para manter SQLite no Render, crie somente um **Web Service** manual a partir do repositório; não sincronize o novo Blueprint com banco. Configure `runtime: docker` e `plan: free`.
3. O `render.yaml` já define `COLONIA_SELF_REGISTER=1`: **não é preciso configurar código de ativação nem criar usuário pelo terminal**. Em um serviço existente, confira em **Environment** que `COLONIA_SELF_REGISTER` está definido como `1`; se o serviço não estiver sincronizado com o Blueprint, adicione essa variável manualmente. A variável antiga `COLONIA_DEMO_MODE` pode ser removida depois.
4. Aguarde a implantação e abra o endereço `https://...onrender.com`. O Render fornece `RENDER_EXTERNAL_HOSTNAME` e `RENDER_EXTERNAL_URL`, que o projeto usa para aceitar o host e a origem do primeiro acesso e do login. O cookie de sessão é `Secure`.
5. A página abre sempre no **login**. Clique em **Não tenho cadastro**, crie uma conta e **guarde o código de recuperação** apresentado. Volte ao login e entre com usuário e senha. Para testar **Esqueci a senha**, informe usuário, código de recuperação e nova senha; anote o novo código que substituirá o anterior. Use **Encerrar sessão** para sair. Confira `/api/health`, os 14 quartos e uma reserva fictícia. O primeiro acesso após inatividade pode demorar enquanto o serviço gratuito desperta.

O cadastro público do Render permite que **qualquer visitante crie uma conta com acesso de recepção a todos os dados**; use somente dados fictícios e desative `COLONIA_SELF_REGISTER` após a apresentação. A mudança não apaga usuários nem redefine senhas. Contas antigas podem entrar normalmente; para habilitar **Esqueci a senha** nelas, entre com a conta e gere um código em **Minha conta → Código de recuperação**. Sem senha e sem código guardado, a recuperação automática não é possível; será necessária intervenção do responsável. No plano gratuito, o banco SQLite é efêmero; se for recriado vazio, será preciso cadastrar as contas novamente.

Para usar um domínio próprio ou outro proxy, configure `COLONIA_HOSTS` com os hosts permitidos e `COLONIA_PUBLIC_URL` com a origem HTTPS esperada no login. Não configure uma origem curinga. A implantação remota depende da sua conta no Render e **não foi executada neste ambiente**.

## Relação com o Sistema Colônia original

O original Tkinter e seus arquivos TXT permanecem no local anterior. Foram reaproveitados o domínio de hospedagem, prédios/quartos, entrada/saída e organização da recepção. A nova regra de preço é por andar/noite; não usa a tabela antiga por prédio/quantidade. Não há importação automática dos TXT: eles não possuem datas e acompanhantes suficientes para uma migração fiel. Uma instalação nova começa com os 14 quartos; hóspedes e reservas começam vazios, salvo os exemplos que você optar por carregar.
