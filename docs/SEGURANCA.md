# Controles e limites de segurança

## Implementados

- Senhas PBKDF2-HMAC-SHA256 com 600.000 iterações e salt aleatório individual. A senha nunca é armazenada em texto puro.
- Sessões aleatórias de 256 bits, persistindo somente hash do token, com validade de oito horas. Logout revoga a sessão; troca de senha revoga todas.
- Cookie HttpOnly, SameSite=Strict e opção Secure para HTTPS.
- Proteção CSRF em toda escrita autenticada. Login, cadastro e recuperação validam a origem quando o navegador a envia.
- Limitação de dez erros de login ou recuperação por conta/origem a cada 15 minutos; o cadastro aberto limita dez contas por origem no mesmo período.
- Cadastro público somente com `COLONIA_SELF_REGISTER=1`. Senhas têm hash PBKDF2; o código de recuperação é aleatório, fica apenas como hash no banco e aparece na tela uma única vez. A recuperação exige usuário e código, revoga as sessões existentes e substitui o código utilizado por outro. Contas antigas podem gerar código em **Minha conta** após confirmar a senha atual.
- O fluxo antigo de primeiro acesso pela API permanece para instalações fechadas, mas é desabilitado quando o cadastro público está ativo e não aparece mais na interface.
- Consultas parametrizadas; nomes de tabelas/colunas são definidos pelo código, não pelo usuário.
- DTOs rejeitam campos desconhecidos, CPF inválido, dinheiro com casas excedentes e entradas fora dos limites.
- HTML gerado a partir de texto de usuários passa por escape. Nenhum dado de hóspedes é interpolado como HTML confiável.
- CSP, X-Frame-Options, nosniff, cache desabilitado e política de referência. Swagger tem CSP específica para seus recursos externos.
- CPF mascarado nas listagens; eventos de auditoria armazenam IDs, ação e usuário, sem CPF/endereço/senha. Access logs do Uvicorn são desabilitados pela aplicação para que buscas por CPF não sejam registradas na query string.
- Foreign keys, unicidade e transações atômicas preservam relações e impedem saldo excedido e reservas concorrentes.
- Não há senha de usuário padrão, chave bancária ou credenciais reais incluídas.

## Configuração de produção

Configure HTTPS, cookie Secure, host permitido, IP confiável do proxy, volume persistente e backups. Configure os logs do proxy/provedor para omitir query strings, corpos e cabeçalhos de autenticação. Restrinja o acesso ao arquivo do banco no servidor. O banco local e seus backups contêm dados pessoais em formato legível para quem possui acesso ao disco; use criptografia do volume, permissões do sistema e políticas adequadas de retenção.

Todos os usuários autenticados possuem o perfil único de recepção nesta versão. Não há RBAC, recuperação de senha por e-mail ou MFA. **Qualquer pessoa que se cadastre enquanto o cadastro público estiver ativo pode acessar todos os hóspedes e reservas.** Use apenas dados fictícios no Render acadêmico. Para uso real, desative o cadastro público, implemente aprovação/perfis e um canal de recuperação administrado. Quem perder senha e código de recuperação não consegue redefinir a senha sozinho. O código deve ser guardado fora do sistema e não compartilhado. Publicação em escala exige revisão de acesso, monitoração, migração de banco e análise específica do ambiente.

O desenho do código de recuperação segue a orientação de códigos salvos de uso único e armazenados com hash do [NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html) e as recomendações de limitação de tentativas e revogação após redefinição da [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html). Ele **não** substitui uma recuperação por e-mail verificado em uma aplicação de produção.

A validação do `Content-Length` não substitui o limite de tamanho de corpo no proxy para requisições transmitidas em blocos. Configure limite de 128 KB também no proxy. Rotas Swagger dependem de CDN; as telas do sistema usam recursos locais.

Os testes exercitam controles específicos, mas não equivalem a auditoria de segurança ou certificação de conformidade legal. Nenhum dado real do Sistema Colônia foi importado.

## Demonstração no Render gratuito

O `render.yaml` habilita `COLONIA_SELF_REGISTER=1`. A página abre no login; **Não tenho cadastro** cria contas enquanto essa configuração estiver ativa, e **Esqueci a senha** pede o código individual entregue no cadastro. O antigo `COLONIA_DEMO_MODE` pode ser removido do ambiente; com cadastro público ativo, a API antiga de primeiro acesso fica indisponível. Como o SQLite no plano gratuito não possui disco persistente, contas podem desaparecer após recriação da instância. O endereço `onrender.com` é aceito a partir das variáveis oficiais `RENDER_EXTERNAL_HOSTNAME` e `RENDER_EXTERNAL_URL`; domínios personalizados exigem `COLONIA_HOSTS` e `COLONIA_PUBLIC_URL` explícitos. Essa configuração serve para demonstração acadêmica, não para armazenar dados reais de hóspedes.
