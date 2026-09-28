# Plano de preparação para o Render

## Estado auditado em 28/09/2026

- O repositório GitHub tem o aplicativo em `recepia/`. O `render.yaml` anterior está nessa subpasta e descreve apenas o splash; Render procura o Blueprint na raiz do repositório.
- A API é FastAPI, serve landing e painel HTML/JavaScript, e o Dockerfile já escuta em `0.0.0.0:${PORT:-8000}`. O `HEALTHCHECK` da imagem ainda assume porta 8000.
- `docker-compose.yml` é a configuração local: PostgreSQL local atende a Evolution; a API e o worker usam `DATABASE_URL` do `.env` (hoje pode apontar para Neon). URLs `http://evolution:8080` e `http://api:8000` só funcionam na rede Docker local.
- O Compose usa `evoapicloud/evolution-api:latest`, PostgreSQL e volume `evolution_data:/evolution/instances`. O tag `latest` não fixa a versão; o payload de webhook no cliente da API foi escrito para Evolution 2.3.x.
- A API guarda instância única por empresa (`clinicas.evolution_instance_name`) e escolhe o tenant do webhook por esse nome. Mensagens e conversas são gravadas com `clinica_id`; o webhook exige `X-Webhook-Token` fora de `DEBUG`.
- O processo `cron/jobs.py` é contínuo e precisa de serviço separado. Fotos, avatares e logos estão em `/data`, hoje em volumes locais.
- `main.py` executa `init_db()` no import; `init_db()` faz `create_all` e migrações aditivas em PostgreSQL. O deploy deve ser ensaiado com backup do Neon antes do primeiro boot.
- `/health` consulta o banco a cada chamada. Para monitoramento frequente, a rota de liveness deve ser leve; uma rota de readiness separada pode consultar o Neon.
- `.env` está ignorado. OpenRouter e Evolution usam chaves apenas no backend; o frontend usa rotas autenticadas da API. O `render.yaml` não deve conter valores secretos.
- A versão online verificada em 28/09/2026 respondeu 200 em `/health`, mas 404 em `/dashboard/saas.html` e `/api/segmentos`; o código novo ainda não estava publicado ali.

## Arquitetura proposta

1. **API**: Render Web Service Docker, URL pública HTTPS, Neon externo, volume persistente em `/data` para fotos. Um processo por instância.
2. **Evolution**: Render Private Service Docker contínuo, imagem 2.3.7 fixada, PostgreSQL do Neon em banco separado da API, disco persistente em `/evolution/instances`. A API e o worker acessam a Evolution pela rede privada do Render. Uma instância Evolution por tenant dentro desse serviço.
3. **Worker**: Render Background Worker Docker para `cron/jobs.py`, mesmo Neon e mesma Evolution privada. Apenas uma réplica para evitar envios duplicados.
4. **Splash**: o Blueprint antigo é preservado; uma entrada estática pode ser migrada separadamente se o domínio atual usar o splash.

O Render Free serve apenas para testar uma API sem garantias de continuidade. Evolution, worker e discos persistentes precisam de plano pago. Não haverá PostgreSQL do Render no Blueprint de produção.

## Arquivos previstos

- `render.yaml` na raiz: API, Evolution privada e worker, com `autoDeployTrigger: off`, referências de variáveis sem secrets e discos persistentes.
- `recepia/Dockerfile` e `recepia/docker-entrypoint.sh`: health check com `${PORT:-8000}` e preparo das pastas do disco montado antes de iniciar como usuário sem privilégios.
- `recepia/Dockerfile.evolution`: fixa a imagem Evolution 2.3.7 sem mudar o Compose local.
- `recepia/config.py`, `recepia/services/whatsapp.py`: URL privada da Evolution resolvida a partir do `hostport` fornecido pelo Render, com URL local preservada.
- `recepia/main.py`: `/health` leve e `/ready` para o banco.
- `recepia/.env.example`: nomes de variáveis e exemplos sem credenciais.
- `DEPLOY_RENDER.md`: passos manuais, migrações, URLs, CORS, QR e teste de reinicialização.

## Persistência e migração

- O Neon da API continua como `DATABASE_URL`. A Evolution recebe outra URL Neon, `DATABASE_CONNECTION_URI`, apontando para banco separado. Não se cria banco local de produção.
- O volume `/evolution/instances` será preservado mesmo se parte do auth state estiver no PostgreSQL, pois a configuração oficial da Evolution mantém esse volume. O disco pertence a uma única réplica da Evolution.
- O volume `/data` preserva fotos, avatares e logos. Migrar arquivos existentes para esse volume requer transferência manual antes de trocar o serviço atual; novas tabelas no Neon não substituem esses arquivos.
- Nenhum deploy nem migração será executado nesta preparação. Após backup e ensaio, o operador preencherá as variáveis no Render e acionará o primeiro deploy manualmente.

## Verificação local concluída

- `pytest -q --disable-warnings`: 299 testes passaram.
- Ruff `--select F`, smoke JavaScript, `docker compose config --quiet`, build Docker da API e da Evolution 2.3.7 passaram.
- A imagem da API inicializou isolada da rede com banco SQLite e credenciais fictícias.
- `render.yaml` passou na validação do JSON Schema oficial do Render. A validação semântica da CLI precisa de um workspace ID e não foi executada; nenhum recurso Render foi criado.
