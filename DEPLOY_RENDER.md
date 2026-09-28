# Deploy da Recepia no Render

Este guia prepara o repositório `RENANOLIVEIRA01996/automa-o-para-ia-atente`. O aplicativo fica em `recepia/`; o Blueprint completo fica em `render.yaml` na raiz. O `recepia/render.yaml` antigo, apenas do splash, permanece preservado. Fazer push não cria serviços novos no Render; se um serviço já estiver vinculado à mesma branch com deploy automático, o push pode atualizá-lo. Criar o Blueprint no painel do Render inicia o primeiro deploy; faça isso somente quando quiser publicar.

## Arquitetura e limites

| Serviço | Tipo Render | Dados persistentes |
| --- | --- | --- |
| `recepia-saas-api` | Web Service Docker pago | Neon (`DATABASE_URL`) e disco `/data` para fotos, avatares e logos |
| `recepia-saas-evolution` | Private Service Docker pago, Evolution 2.3.7 | Neon separado (`DATABASE_CONNECTION_URI`) e disco `/evolution/instances` |
| `recepia-saas-worker` | Background Worker Docker pago, uma réplica | Mesmo Neon da API; executa lembretes e tarefas programadas |

Evolution não recebe URL pública. A API e o worker chegam a ela pela rede privada do Render; a Evolution envia webhooks por HTTPS para a API pública. Todos os serviços devem ficar na **mesma região e workspace**. O Blueprint usa nomes novos e não aponta domínios existentes, para não substituir a versão online atual durante o ensaio.

O plano Free pode servir para um teste isolado da API, mas hiberna após inatividade, perde arquivos locais em reinícios e não aceita disco persistente. Ele não atende ao objetivo de WhatsApp contínuo com worker e sessões preservadas. Render documenta essas limitações em [Free](https://render.com/docs/free), [Persistent Disks](https://render.com/docs/disks) e [Private Services](https://render.com/docs/private-services). Não use ping interno para contorná-las.

## Antes do primeiro deploy

1. Crie uma conta/workspace no [Render](https://dashboard.render.com/) e conecte o GitHub. Selecione `RENANOLIVEIRA01996/automa-o-para-ia-atente`, branch `main`.
2. No Neon, mantenha o banco atual da Recepia. Faça backup ou crie uma branch para ensaiar as migrações. Crie **outro banco ou projeto Neon** para a Evolution, sem misturar tabelas Prisma com as tabelas da Recepia. Não apague o banco existente.
3. Guarde as URLs de conexão Neon em local seguro. Para a API, use `DATABASE_URL` do Neon com TLS (`sslmode=require`); o código também exige TLS automaticamente para hosts `*.neon.tech` quando a URL não explicita `sslmode`. Para Evolution, use a URL do banco separado em `DATABASE_CONNECTION_URI`, também com TLS. Confira [conexões Neon](https://neon.com/docs/get-started-with-neon/workflow-primer).
4. Antes de aplicar o esquema à base existente, ensaie em branch/staging Neon. O código anterior executava `init_db()` em todo import da API; o Blueprint põe `RUN_DB_MIGRATIONS_ON_STARTUP=false`. Depois do backup e ensaio, execute **manualmente**, a partir de `recepia/`, com a URL correta no ambiente: `python scripts/prepare_database.py --apply`. Esse comando faz `create_all`, `ALTER TABLE ... IF NOT EXISTS` e backfills existentes; não há Alembic versionado. Não o execute contra produção sem conferir o alvo e o backup.
5. Se já há instâncias WhatsApp no PC, salve **também** o banco PostgreSQL usado pela Evolution local e o conteúdo do volume Docker `evolution_data` (`/evolution/instances`). O Neon da Recepia, sozinho, não contém todo o estado da Evolution. Migre banco e volume para o serviço novo antes de esperar que sessões antigas reconectem. Se iniciar a Evolution com banco/disco novos, cada número precisará de um primeiro QR. Não há migração automática desse estado.
6. Se há fotos, avatares ou logos locais, transfira os volumes `recepia_fotos`, `recepia_avatares` e `recepia_logos` para o disco `/data` do novo serviço, mantendo respectivamente as pastas `fotos`, `fotos_paciente` e `logos`. Sem isso, registros do Neon podem apontar para arquivos ausentes. O [guia de discos do Render](https://render.com/docs/disks) descreve transferência por SSH/SCP.

## Variáveis do Blueprint

Na tela do Render mostrada pelo usuário, clique **+ New → Blueprint** (também há **Blueprints** no menu esquerdo). Não é necessário criar um **Project** antes: o Blueprint criará os três serviços no workspace; um Project serve apenas para organizá-los depois. Escolha o repositório e o arquivo `render.yaml` da raiz. Revise planos, região, nomes e discos antes de aplicar. O Blueprint está com `autoDeployTrigger: off`; isso impede deploys automáticos posteriores, mas **não impede o deploy inicial ao criar os serviços**.

Preencha no fluxo inicial os campos `sync: false` abaixo, sem colocar valores no GitHub:

| Serviço | Variável | Valor a fornecer |
| --- | --- | --- |
| API | `DATABASE_URL` | URL do banco Recepia no Neon |
| API | `JWT_SECRET`, `ADMIN_API_KEY` | Segredos fortes; preserve os atuais se quiser manter as credenciais/tokens existentes |
| API | `EVOLUTION_WEBHOOK_SECRET` | Segredo forte para `X-Webhook-Token`; mantenha o mesmo valor ao migrar webhooks existentes |
| API | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Chave e modelo com suporte a ferramentas na conta OpenRouter |
| API | `ALLOWED_ORIGINS` | Origens HTTPS exatas das páginas que acessam a API de outro domínio, separadas por vírgula; por exemplo `https://recepia.app.br,https://app.recepia.app.br` se forem seus frontends |
| Evolution | `AUTHENTICATION_API_KEY` | Chave forte da Evolution; preserve a atual se estiver migrando instâncias |
| Evolution | `DATABASE_CONNECTION_URI` | URL Neon do banco **separado** da Evolution |

O Blueprint encaminha automaticamente a chave da Evolution para a API/worker e copia as credenciais necessárias da API para o worker. `EVOLUTION_API_HOSTPORT` vem do endereço privado do Render. `PUBLIC_WEBHOOK_URL` e `APP_URL` recebem inicialmente a URL `onrender.com` da API. `OPENROUTER_BASE_URL` é `https://openrouter.ai/api/v1`; `AI_PROVIDER` é `openrouter`. Se faltar chave ou modelo, a rota de conectar WhatsApp retorna erro claro em produção.

Variáveis com `sync: false` são solicitadas somente na **criação inicial** do Blueprint. Se adicionar ou mudar uma depois, edite as variáveis do serviço no painel do Render; veja a [referência do Blueprint](https://render.com/docs/blueprint-spec). Não use `*` em `ALLOWED_ORIGINS` em produção. Se vincular domínio próprio à API, atualize `PUBLIC_WEBHOOK_URL`, `APP_URL` e `ALLOWED_ORIGINS` no painel e execute a sincronização dos webhooks; o valor automático do Blueprint continua apontando para `onrender.com` até você trocar a referência no arquivo.

O nome do campo de chave da Evolution no painel é `AUTHENTICATION_API_KEY`; o Blueprint o entrega à API como `EVOLUTION_API_KEY`. O segredo de webhook é outro valor, independente. A chave OpenRouter fica **somente na API**. Não copie nenhuma dessas chaves para arquivos HTML, JavaScript ou para o repositório.

## Primeiro deploy e checagens

1. Aplique o Blueprint apenas após os preparos acima. Espere Evolution e worker iniciarem e a API estar saudável. A API escuta `0.0.0.0:$PORT`; a Evolution escuta 8080 apenas na rede privada.
2. Abra `https://URL-DA-API/health`: deve retornar HTTP 200 e `{"status":"ok"}` sem consultar IA nem banco. Abra `/ready`: deve retornar HTTP 200 com banco `ok`; HTTP 503 significa que o Neon ou o esquema ainda não está pronto. Verifique logs sem copiar segredos.
   Confirme também que o serviço consegue gravar em `/data/fotos`, `/data/fotos_paciente` e `/data/logos`; o entrypoint da imagem ajusta o dono das pastas após o disco ser montado.
3. Abra `https://URL-DA-API/dashboard/`. Faça login; o painel SaaS redireciona para `/dashboard/saas.html`. Confirme `/api/segmentos` com autenticação conforme a API e carregue agenda/clientes.
4. No Render, confirme que os três serviços estão na mesma região. Confira o endereço privado da Evolution em **Connect → Internal** e compare com o `EVOLUTION_API_HOSTPORT` resolvido para API/worker. A Evolution não terá URL pública.
5. Para uma empresa, abra **WhatsApp → Conectar**. A API usa a `evolution_instance_name` exclusiva desse tenant, cria/recupera a instância, configura o webhook em `PUBLIC_WEBHOOK_URL/api/webhook/evolution` e retorna o QR. Escaneie no WhatsApp do próprio cliente.
6. Em outra conta/número, envie uma mensagem. Confirme evento recebido no webhook, conversa associada ao tenant correto, resposta da IA via OpenRouter e agendamento no Neon. Faça o mesmo com uma segunda empresa para verificar isolamento. Não use o mesmo número em duas instâncias.
7. Se mudou a URL pública depois de conectar números, execute no shell da API, em `/app`: `python scripts/sync_evolution_webhooks.py` para contar instâncias e depois `python scripts/sync_evolution_webhooks.py --apply` para reapontar os webhooks existentes. O script não cria nem apaga instâncias.

## Teste obrigatório de reinicialização

Depois do primeiro QR e de uma mensagem respondida:

1. Confirme que `/api/whatsapp/status` da empresa indica conexão e que a instância foi gravada no banco Evolution.
2. Envie uma mensagem de outro número e confirme webhook, conversa e resposta.
3. Reinicie **apenas a Evolution** no painel Render. Aguarde a inicialização; confira se a instância volta a `open` sem novo QR.
4. Reinicie **apenas a API**. Confira `/health`, `/ready` e status da instância.
5. Envie outra mensagem e confirme nova resposta da IA. Repita com uma segunda empresa.
6. Se reconectar falhar, confira primeiro banco Evolution, disco `/evolution/instances`, logs da versão 2.3.7, chave e URL privada. Não apague instância nem faça logout para tentar corrigir reinicialização: logout invalida a sessão.

O teste acima exige serviços criados e números reais; ele **não foi executado nesta preparação**. Uma migração da Evolution local para a nova instância do Render exige restaurar banco/volume antes de testar persistência de sessões antigas.

## Desenvolvimento local e validação

O `recepia/docker-compose.yml` original continua para desenvolvimento local, com `postgres`, `evolution`, `api` e `worker`. No `.env` local, `EVOLUTION_API_URL=http://evolution:8080` e `PUBLIC_WEBHOOK_URL=http://api:8000` são URLs da rede Docker; em produção são substituídas pelo host privado do Render e pela URL HTTPS pública da API. Não sobrescreva seu `.env` real. O `recepia/.env.example` é apenas um modelo seguro.

Da pasta `recepia/`:

```text
python -m pytest -q
python -m ruff check . --select F
node tests/segment_ui_smoke.cjs
docker compose config --quiet
docker build -t recepia-api-local .
```

Para testar localmente a API sem Docker, mantenha o `.env` atual e rode `uvicorn main:app --host 0.0.0.0 --port 8000`. Nenhum teste automatizado deste guia acessa OpenRouter, Evolution ou Neon reais. O `render.yaml` antigo do splash foi preservado; a troca de domínios da versão online atual deve ser feita separadamente e com verificação de DNS.
