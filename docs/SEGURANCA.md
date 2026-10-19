# Controles e limites de segurança

## Implementados

- Senhas PBKDF2-HMAC-SHA256 com 600.000 iterações e salt aleatório individual. A senha nunca é armazenada em texto puro.
- Sessões aleatórias de 256 bits, persistindo somente hash do token, com validade de oito horas. Logout revoga a sessão; troca de senha revoga todas.
- Cookie HttpOnly, SameSite=Strict e opção Secure para HTTPS.
- Proteção CSRF em toda escrita autenticada. Login valida a origem quando o navegador a envia.
- Limitação de dez erros de login por conta ou origem a cada 15 minutos, armazenada no banco.
- Consultas parametrizadas; nomes de tabelas/colunas são definidos pelo código, não pelo usuário.
- DTOs rejeitam campos desconhecidos, CPF inválido, dinheiro com casas excedentes e entradas fora dos limites.
- HTML gerado a partir de texto de usuários passa por escape. Nenhum dado de hóspedes é interpolado como HTML confiável.
- CSP, X-Frame-Options, nosniff, cache desabilitado e política de referência. Swagger tem CSP específica para seus recursos externos.
- CPF mascarado nas listagens; eventos de auditoria armazenam IDs, ação e usuário, sem CPF/endereço/senha. Access logs do Uvicorn são desabilitados pela aplicação para que buscas por CPF não sejam registradas na query string.
- Foreign keys, unicidade e transações atômicas preservam relações e impedem saldo excedido e reservas concorrentes.
- Não há senha padrão, chave bancária ou credenciais reais incluídas.

## Configuração de produção

Configure HTTPS, cookie Secure, host permitido, IP confiável do proxy, volume persistente e backups. Configure os logs do proxy/provedor para omitir query strings, corpos e cabeçalhos de autenticação. Restrinja o acesso ao arquivo do banco no servidor. O banco local e seus backups contêm dados pessoais em formato legível para quem possui acesso ao disco; use criptografia do volume, permissões do sistema e políticas adequadas de retenção.

Todos os usuários autenticados possuem o perfil único de recepção nesta versão. Não há RBAC, recuperação de senha por e-mail ou MFA. A conta é criada por administração local. Publicação em escala exige revisão de acesso, monitoração, migração de banco e análise específica do ambiente.

A validação do `Content-Length` não substitui o limite de tamanho de corpo no proxy para requisições transmitidas em blocos. Configure limite de 128 KB também no proxy. Rotas Swagger dependem de CDN; as telas do sistema usam recursos locais.

Os testes exercitam controles específicos, mas não equivalem a auditoria de segurança ou certificação de conformidade legal. Nenhum dado real do Sistema Colônia foi importado.

## Demonstração no Render gratuito

O `render.yaml` solicita `COLONIA_ADMIN_PASSWORD` como variável secreta; não armazene a senha no Git. A conta é recriada automaticamente ao iniciar um banco vazio, pois o SQLite no plano gratuito não possui disco persistente. Configure uma senha exclusiva de pelo menos 12 caracteres e use somente hóspedes fictícios. O endereço `onrender.com` é aceito a partir das variáveis oficiais `RENDER_EXTERNAL_HOSTNAME` e `RENDER_EXTERNAL_URL`; domínios personalizados exigem `COLONIA_HOSTS` e `COLONIA_PUBLIC_URL` explícitos. Essa configuração serve para demonstração acadêmica, não para armazenar dados reais de hóspedes.
