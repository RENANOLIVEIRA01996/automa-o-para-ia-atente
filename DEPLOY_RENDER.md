# Teste gratuito da Recepia no Render

O `render.yaml` da raiz cria **um único Web Service Free** para o painel e a API. Ele não cria Evolution, worker, banco Render nem disco. O código local em `recepia/` e o Compose continuam independentes. Criar o Blueprint inicia o primeiro deploy; `autoDeployTrigger: "off"` desliga os deploys automáticos posteriores.

## Por que a tela anterior pediu cartão

O Blueprint anterior continha serviços pagos e discos. Essa configuração foi removida da branch `main`. Na tela já aberta do Render, feche o aviso de pagamento, atualize a página e, se necessário, recomece **+ New → Blueprint** para buscar a versão nova do GitHub. Confirme que a prévia mostra **somente `recepia-saas-api`, plano Free e nenhum disco** antes de criar. O Render [permite Web Services Free](https://render.com/docs/free); se a prévia ainda pedir pagamento, não confirme e confira se selecionou a branch `main` atualizada.

## O que funciona neste Blueprint

- O painel e a API ficam em uma URL `https://recepia-saas-api.onrender.com` (o Render pode ajustar o nome se já estiver ocupado).
- Os dados de tabelas permanecem no **Neon existente**, via `DATABASE_URL`.
- A IA usa OpenRouter quando as variáveis abaixo estão configuradas.

O Render Free [hiberna após 15 minutos sem tráfego](https://render.com/docs/free), e a primeira requisição após isso pode levar cerca de um minuto. Também [não oferece disco persistente](https://render.com/docs/free): uploads de fotos, avatares e logos ficam desativados pelo Blueprint para evitar perda silenciosa de arquivos. O worker de lembretes não é criado, então tarefas programadas não rodam. O Blueprint não hospeda a Evolution; WhatsApp só poderá conectar depois de configurar uma Evolution **externa e alcançável pela internet**. Mesmo com ela, a hibernação da API gratuita pode atrasar ou causar timeout no webhook. Não use esta configuração para prometer atendimento WhatsApp contínuo.

## Antes de clicar em Deploy Blueprint

1. No Render, escolha `RENANOLIVEIRA01996/automa-o-para-ia-atente`, branch `main`. O Blueprint está em `render.yaml` na raiz. Não é preciso criar um Project antes.
2. Confira a prévia: **um Web Service Free**, sem Private Service, Background Worker, Postgres Render ou disco.
3. Faça backup do banco Neon existente. O Blueprint define `RUN_DB_MIGRATIONS_ON_STARTUP=false`, então subir a API não altera o esquema automaticamente. Se `/ready` indicar esquema desatualizado, ensaie as migrações em branch Neon e execute localmente, de `recepia/`, `python scripts/prepare_database.py --apply` apenas depois de conferir o alvo e o backup. O plano Free não fornece shell no serviço.

## Chaves solicitadas na criação

O Render solicita os sete campos `sync: false` abaixo. Copie os valores **diretamente** de `recepia/.env` local para o painel do Render; não os envie por chat nem faça commit do `.env`.

| Campo no Render | Origem |
| --- | --- |
| `DATABASE_URL` | `.env`, linha 11: banco Recepia no Neon |
| `JWT_SECRET` | `.env`, linha 16 |
| `ADMIN_API_KEY` | `.env`, linha 19 |
| `EVOLUTION_WEBHOOK_SECRET` | `.env`, linha 26; é exigido para proteger o endpoint, mesmo antes de ligar a Evolution |
| `OPENROUTER_API_KEY` | `.env`, linha 36 |
| `OPENROUTER_MODEL` | `.env`, linha 41; um exemplo com suporte a ferramentas é [`openai/gpt-4.1-mini`](https://openrouter.ai/openai/gpt-4.1-mini) |
| `ALLOWED_ORIGINS` | Origens HTTPS dos frontends, por exemplo `https://recepia.app.br,https://app.recepia.app.br`; remova `localhost` |

`PUBLIC_WEBHOOK_URL` e `APP_URL` recebem a URL `onrender.com` da própria API. `EVOLUTION_API_URL` e `EVOLUTION_API_KEY` começam vazios para não tentar usar a Evolution local do PC. As variáveis com `sync: false` são solicitadas [somente na criação inicial](https://render.com/docs/blueprint-spec); depois, altere-as em **recepia-saas-api → Environment**.

## Após o primeiro deploy

1. Abra a URL exibida pelo Render e depois `/health` (HTTP 200) e `/ready` (HTTP 200 se o Neon estiver acessível). Abra `/dashboard/` e faça login.
2. Se usar frontend em outro domínio, ajuste `ALLOWED_ORIGINS` em **Environment**. Para domínio próprio, também ajuste `APP_URL` e `PUBLIC_WEBHOOK_URL` após a mudança.
3. Para tentar WhatsApp, hospede a Evolution separadamente com persistência de banco e sessão. Em **recepia-saas-api → Environment**, configure `EVOLUTION_API_URL` com URL HTTPS pública da Evolution e `EVOLUTION_API_KEY` com a chave dela. O `PUBLIC_WEBHOOK_URL` precisa ser alcançável pela Evolution. A Evolution local em `http://evolution:8080` ou `localhost` não é acessível pelo Render.

Mesmo com Evolution externa, a API Free não tem disponibilidade contínua: valide cada webhook e resposta com um número de teste. As fotos antigas armazenadas só no PC não aparecerão no Render. O `recepia/docker-compose.yml` continua disponível para desenvolvimento local com banco, Evolution, API e worker.
