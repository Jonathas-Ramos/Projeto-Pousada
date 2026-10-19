# Controles e limites de segurança

## Implementados

- Senhas PBKDF2-HMAC-SHA256 com 600.000 iterações e salt aleatório individual. A senha nunca é armazenada em texto puro.
- Sessões aleatórias de 256 bits, persistindo somente hash do token, com validade de oito horas. Logout revoga a sessão; troca de senha revoga todas.
- Cookie HttpOnly, SameSite=Strict e opção Secure para HTTPS.
- Proteção CSRF em toda escrita autenticada. Login valida a origem quando o navegador a envia.
- Limitação de dez erros de login por conta ou origem a cada 15 minutos, armazenada no banco.
- Primeiro acesso pela interface somente enquanto a tabela de usuários estiver vazia. Fora do modo de apresentação, exige `COLONIA_SETUP_CODE` secreto de 16 a 200 caracteres. No modo de apresentação, o código fixo é exibido publicamente e **não oferece controle de acesso ao primeiro cadastro**. A comparação é constante, erros são limitados por origem, e a criação usa transação de escrita para impedir duas primeiras contas simultâneas. O evento é auditado sem registrar código ou senha.
- Consultas parametrizadas; nomes de tabelas/colunas são definidos pelo código, não pelo usuário.
- DTOs rejeitam campos desconhecidos, CPF inválido, dinheiro com casas excedentes e entradas fora dos limites.
- HTML gerado a partir de texto de usuários passa por escape. Nenhum dado de hóspedes é interpolado como HTML confiável.
- CSP, X-Frame-Options, nosniff, cache desabilitado e política de referência. Swagger tem CSP específica para seus recursos externos.
- CPF mascarado nas listagens; eventos de auditoria armazenam IDs, ação e usuário, sem CPF/endereço/senha. Access logs do Uvicorn são desabilitados pela aplicação para que buscas por CPF não sejam registradas na query string.
- Foreign keys, unicidade e transações atômicas preservam relações e impedem saldo excedido e reservas concorrentes.
- Não há senha de usuário padrão, chave bancária ou credenciais reais incluídas. O código público de demonstração não é uma senha de usuário.

## Configuração de produção

Configure HTTPS, cookie Secure, host permitido, IP confiável do proxy, volume persistente e backups. Configure os logs do proxy/provedor para omitir query strings, corpos e cabeçalhos de autenticação. Restrinja o acesso ao arquivo do banco no servidor. O banco local e seus backups contêm dados pessoais em formato legível para quem possui acesso ao disco; use criptografia do volume, permissões do sistema e políticas adequadas de retenção.

Todos os usuários autenticados possuem o perfil único de recepção nesta versão. Não há RBAC, recuperação de senha por e-mail ou MFA. A primeira conta pode ser criada na interface; a administração local continua disponível. Fora do modo de apresentação, o código secreto deve ser entregue apenas ao responsável e não deve ser publicado. Publicação em escala exige revisão de acesso, monitoração, migração de banco e análise específica do ambiente.

A validação do `Content-Length` não substitui o limite de tamanho de corpo no proxy para requisições transmitidas em blocos. Configure limite de 128 KB também no proxy. Rotas Swagger dependem de CDN; as telas do sistema usam recursos locais.

Os testes exercitam controles específicos, mas não equivalem a auditoria de segurança ou certificação de conformidade legal. Nenhum dado real do Sistema Colônia foi importado.

## Demonstração no Render gratuito

O `render.yaml` habilita `COLONIA_DEMO_MODE=1` e dispensa a configuração de segredo. O código `APRESENTACAO2026` aparece na página quando o banco está vazio. Isso facilita a apresentação, mas permite que qualquer visitante crie a primeira conta antes do responsável; **não use dados reais**. Após a primeira conta, o cadastro fecha e login/logout continuam exigindo usuário e senha. O modo de demonstração prevalece sobre eventuais variáveis antigas `COLONIA_SETUP_CODE` e `COLONIA_ADMIN_*`; não apaga contas já existentes. Para uso fora da apresentação, desative `COLONIA_DEMO_MODE` e configure `COLONIA_SETUP_CODE` secreto (16 a 200 caracteres) no ambiente, sem publicá-lo no Git. Como o SQLite no plano gratuito não possui disco persistente, a conta pode desaparecer após recriação da instância e exigir novo primeiro acesso. O endereço `onrender.com` é aceito a partir das variáveis oficiais `RENDER_EXTERNAL_HOSTNAME` e `RENDER_EXTERNAL_URL`; domínios personalizados exigem `COLONIA_HOSTS` e `COLONIA_PUBLIC_URL` explícitos. Essa configuração serve para demonstração acadêmica, não para armazenar dados reais de hóspedes.
