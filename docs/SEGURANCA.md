# Controles e limites de segurança

## Implementados

- Senhas PBKDF2-HMAC-SHA256 com 600.000 iterações e salt aleatório individual. A senha nunca é armazenada em texto puro.
- Sessões aleatórias de 256 bits, persistindo somente hash do token, com validade de oito horas. Logout revoga a sessão; troca de senha revoga todas.
- Cookie HttpOnly, SameSite=Strict e opção Secure para HTTPS.
- Proteção CSRF em toda escrita autenticada. Login valida a origem quando o navegador a envia.
- Limitação de dez erros de login por conta ou origem a cada 15 minutos, armazenada no banco.
- Primeiro acesso pela interface somente enquanto a tabela de usuários estiver vazia e mediante `COLONIA_SETUP_CODE` secreto de 16 a 200 caracteres. A comparação é constante, erros são limitados por origem, e a criação usa transação de escrita para impedir duas primeiras contas simultâneas. O evento é auditado sem registrar código ou senha.
- Consultas parametrizadas; nomes de tabelas/colunas são definidos pelo código, não pelo usuário.
- DTOs rejeitam campos desconhecidos, CPF inválido, dinheiro com casas excedentes e entradas fora dos limites.
- HTML gerado a partir de texto de usuários passa por escape. Nenhum dado de hóspedes é interpolado como HTML confiável.
- CSP, X-Frame-Options, nosniff, cache desabilitado e política de referência. Swagger tem CSP específica para seus recursos externos.
- CPF mascarado nas listagens; eventos de auditoria armazenam IDs, ação e usuário, sem CPF/endereço/senha. Access logs do Uvicorn são desabilitados pela aplicação para que buscas por CPF não sejam registradas na query string.
- Foreign keys, unicidade e transações atômicas preservam relações e impedem saldo excedido e reservas concorrentes.
- Não há senha padrão, chave bancária ou credenciais reais incluídas.

## Configuração de produção

Configure HTTPS, cookie Secure, host permitido, IP confiável do proxy, volume persistente e backups. Configure os logs do proxy/provedor para omitir query strings, corpos e cabeçalhos de autenticação. Restrinja o acesso ao arquivo do banco no servidor. O banco local e seus backups contêm dados pessoais em formato legível para quem possui acesso ao disco; use criptografia do volume, permissões do sistema e políticas adequadas de retenção.

Todos os usuários autenticados possuem o perfil único de recepção nesta versão. Não há RBAC, recuperação de senha por e-mail ou MFA. A primeira conta pode ser criada na interface com código de ativação; a administração local continua disponível. O código deve ser entregue apenas ao responsável e não deve ser publicado. Publicação em escala exige revisão de acesso, monitoração, migração de banco e análise específica do ambiente.

A validação do `Content-Length` não substitui o limite de tamanho de corpo no proxy para requisições transmitidas em blocos. Configure limite de 128 KB também no proxy. Rotas Swagger dependem de CDN; as telas do sistema usam recursos locais.

Os testes exercitam controles específicos, mas não equivalem a auditoria de segurança ou certificação de conformidade legal. Nenhum dado real do Sistema Colônia foi importado.

## Demonstração no Render gratuito

O `render.yaml` solicita `COLONIA_SETUP_CODE` como segredo; não armazene seu valor no Git. Em Blueprint já existente, configure o segredo manualmente em **Environment**, pois `sync: false` só solicita o valor na criação inicial. Até isso ocorrer, um serviço antigo mantém o provisionamento por `COLONIA_ADMIN_*` para não perder o login anterior. Com o código configurado, um banco vazio mostra o formulário de primeiro acesso e a pessoa cria sua própria senha de pelo menos 12 caracteres. Como o SQLite no plano gratuito não possui disco persistente, a conta pode desaparecer após recriação da instância e exigir novo primeiro acesso; use somente hóspedes fictícios. O endereço `onrender.com` é aceito a partir das variáveis oficiais `RENDER_EXTERNAL_HOSTNAME` e `RENDER_EXTERNAL_URL`; domínios personalizados exigem `COLONIA_HOSTS` e `COLONIA_PUBLIC_URL` explícitos. Essa configuração serve para demonstração acadêmica, não para armazenar dados reais de hóspedes.
