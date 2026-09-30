# Recepia em duas VMs Oracle E2 Micro Always Free

Esta é a alternativa provisória quando não há capacidade A1 na região principal.
Cada `VM.Standard.E2.1.Micro` tem apenas 1 GiB de RAM e 1/8 de OCPU. A implantação
só deve ser considerada pronta após os testes de carga, WhatsApp e reinício.

## Arquitetura e custo

As duas VMs ficam na região principal `sa-saopaulo-1`, na VCN `recepia-vcn`:

- **VM API:** Caddy/HTTPS, Recepia API e um único worker de agendamentos. A API
  escuta em `0.0.0.0:8000` dentro do contêiner; a porta do host é vinculada
  somente ao IP privado. Fotos, avatares, logos e certificados usam volumes.
- **VM Evolution:** Evolution API v2.3.7/Baileys e PostgreSQL 16 exclusivo da
  Evolution. O banco e os arquivos da sessão usam volumes persistentes.
- **Externos:** Neon PostgreSQL para dados multi-tenant e OpenRouter para IA.

As VMs usam 50 GiB de boot cada, 100 GiB no total dos 200 GiB Always Free. Cada
uma tem 2 GiB de swap como arquivo **dentro** do volume de boot, sem criar discos
extras. Não crie uma terceira E2 Micro, outra shape, balanceador pago ou volume
fora da franquia. Verifique os limites e o inventário antes de novos recursos.

Somente 80/443 da VM API ficam públicos. A regra da VCN permite 22/tcp do IP do
administrador e 22, 8000 e 8080/tcp apenas da sub-rede privada. As portas 5432,
8000 e 8080 não são publicadas em IP público. A segunda VM possui IP público
para baixar pacotes e imagens, mas não publica Evolution nele.

## Preparar e acessar o Ubuntu

Use Ubuntu 24.04 AMD64 e a mesma chave SSH cadastrada nas duas VMs. No computador
do administrador:

```bash
ssh -i CAMINHO_DA_CHAVE ubuntu@IP_PUBLICO_API
ssh -i CAMINHO_DA_CHAVE ubuntu@IP_PUBLICO_EVOLUTION
```

Em cada VM, execute `sudo bash ~/recepia/scripts/oracle-setup.sh` após copiar
o projeto. O script instala somente Git,
OpenSSL, Docker Engine, Buildx e Compose Plugin, e habilita Docker no boot.
Confirme `sudo docker compose version` e `sudo systemctl is-enabled docker`.

Se a memória impedir o build, o swap no boot volume pode evitar OOM, mas não
aumenta CPU nem RAM. Com swap, a resposta pode ficar lenta; monitore uso real.

## Código e segredos

Os arquivos `docker-compose.production.api.yml` e
`docker-compose.production.evolution.yml` são independentes. Copie o código de
forma segura para `~/recepia` em cada VM. Não envie `.env` pelo Git nem incorpore
segredos à imagem Docker. Na VM API, `.env` precisa conter `DATABASE_URL` Neon
com TLS, OpenRouter, segredos da aplicação, `DOMAIN`, `APP_URL`,
`ALLOWED_ORIGINS`, `API_PRIVATE_IP`, `EVOLUTION_PRIVATE_IP` e
`EVOLUTION_API_KEY`. Para ativar o fallback do atendimento, configure
`GROQ_API_KEY` na VM API; o modelo padrão é `GROQ_FALLBACK_MODEL=openai/gpt-oss-20b`.
Na VM Evolution, `.env` precisa de
`POSTGRES_PASSWORD`, `EVOLUTION_API_KEY` e ambos os IPs privados. O valor de
`EVOLUTION_API_KEY` precisa ser idêntico nas duas VMs. Proteja cada `.env` com
`chmod 600`. Gere segredos distintos com `openssl rand -hex 32`; não cole valores
em comandos gravados no histórico, documentação ou mensagens.

O nome público pode ser um hostname temporário gratuito de
[sslip.io](https://sslip.io/), por exemplo `recepia.IP-COM-HIFENS.sslip.io`.
Configure `APP_URL` e `ALLOWED_ORIGINS` com `https://` e o mesmo hostname.
O Caddy emite HTTPS depois que o DNS resolver para o IP público da VM API.

## Iniciar e verificar

Na VM Evolution:

```bash
cd ~/recepia
sudo docker compose -f docker-compose.production.evolution.yml config --quiet
sudo docker compose -f docker-compose.production.evolution.yml up -d
sudo docker compose -f docker-compose.production.evolution.yml ps
```

Na VM API, após a Evolution ficar saudável e com o status real das sessões
conferido no Neon:

```bash
cd ~/recepia
sudo docker compose -f docker-compose.production.api.yml config --quiet
sudo docker compose -f docker-compose.production.api.yml up -d
sudo docker compose -f docker-compose.production.api.yml ps
sudo docker compose -f docker-compose.production.api.yml exec -T api curl -fsS http://127.0.0.1:8000/ready
```

No computador do administrador, confira `https://DOMINIO/health` e o painel.
Em cada VM, use `sudo docker stats --no-stream`, `free -m`, `df -h /` e
`sudo docker compose -f ARQUIVO.yml logs --tail=100` para verificar memória,
swap, disco e erros. `/health` testa o processo; `/ready` testa a conexão Neon.
O healthcheck do worker é desativado porque ele não oferece HTTP; confirme o
processo e o log `Recepia scheduler iniciado`. Somente **um** worker pode rodar.
Antes de iniciá-lo, confira se cada `clinicas.evolution_conectado` corresponde
ao estado real da instância Evolution. O agendador registra confirmações como
enviadas antes de chamar a Evolution; uma flag antiga com sessão desconectada
pode causar perda de lembretes.

## WhatsApp, sessão e reboot

Abra o painel via HTTPS, autentique-se na empresa e use WhatsApp → Conectar
WhatsApp. Escaneie o QR com o celular da empresa. Envie e receba uma mensagem,
teste resposta por IA, webhook, agendamento e lembrete. O webhook Evolution →
Recepia usa o IP privado da VM API e `X-Webhook-Token`.

Se uma sessão Evolution já existe em outro host, migre **juntos** o dump do
PostgreSQL da Evolution e o volume `evolution_data` antes de gerar novo QR.
Copiar só um deles não preserva a sessão. Depois de conectar, reinicie a
Evolution, confirme que continua conectada, reinicie ambas as VMs e repita os
testes. Os contêineres usam `restart: unless-stopped`; Docker inicia no boot.

## Backup, restauração e atualização

Faça backup do Neon fora das VMs e das duas VMs. Proteja os arquivos com
`umask 077`, copie-os cifrados para fora da Oracle e teste a restauração em
ambiente de ensaio. Não use `docker compose down -v`.

Na VM API, faça um dump do Neon com `pg_dump` da mesma versão principal do
servidor Neon (18 na implantação de 29/09/2026). O arquivo `.env` fornece
`DATABASE_URL` apenas ao contêiner efêmero; nunca inclua o arquivo no Git:

```bash
cd ~/recepia
umask 077
mkdir -p ~/recepia-backups
sudo docker run --rm --env-file .env --entrypoint sh postgres:18-alpine \
  -c 'pg_dump -Fc --no-owner --no-acl "$DATABASE_URL"' \
  > ~/recepia-backups/recepia-neon.dump
sudo docker run --rm -v "$HOME/recepia-backups:/backup:ro" \
  --entrypoint pg_restore postgres:18-alpine --list \
  /backup/recepia-neon.dump > /dev/null
```

Na VM Evolution, pare apenas a Evolution durante a cópia consistente; o banco
PostgreSQL continua disponível para o `pg_dump`. O volume da sessão e o dump
devem ter o mesmo ponto no tempo:

```bash
cd ~/recepia
umask 077
mkdir -p ~/recepia-backups
sudo docker compose -f docker-compose.production.evolution.yml stop evolution
sudo docker compose -f docker-compose.production.evolution.yml exec -T postgres \
  pg_dump -U recepia -d evolution -Fc \
  > ~/recepia-backups/evolution.dump
sudo docker run --rm \
  -v recepia-evolution_evolution_data:/data:ro \
  -v "$HOME/recepia-backups:/backup" alpine:3.20 \
  tar -C /data -czf /backup/evolution-data.tar.gz .
sudo docker compose -f docker-compose.production.evolution.yml start evolution
```

Na VM API, copie também os volumes `recepia-api_recepia_fotos`,
`recepia-api_recepia_avatares`, `recepia-api_recepia_logos`,
`recepia-api_caddy_data` e `recepia-api_caddy_config` com o mesmo método
`docker run -v VOLUME:/data:ro ... tar`. Guarde uma cópia protegida do
`.env` de cada VM separadamente dos dumps; sem seus segredos, um restauro
completo de autenticação e webhook não é possível.

Para restaurar, ensaie primeiro em VMs novas e em uma branch Neon de teste.
Restaure o dump Neon com `pg_restore --clean --if-exists --no-owner --no-acl`
apontado para a **branch de teste**. Na VM Evolution nova, suba somente o
PostgreSQL, restaure `evolution.dump` em `evolution` com `pg_restore`,
extraia `evolution-data.tar.gz` em um volume de sessão **vazio** e só então
suba a Evolution. Recupere os volumes da API, configure os `.env` com permissão
`600`, inicie API, worker e Caddy e teste status WhatsApp, webhook e
agendamento. Nunca restaure um dump sobre o Neon de produção sem janela de
manutenção e backup atual.

Para atualizar, faça backup, revise alterações de esquema e imagens, transfira
o código novo, reconstrua somente a API e suba os dois Compose. Não execute
migrações Neon automaticamente: `RUN_DB_MIGRATIONS_ON_STARTUP=false`.
O guia [ORACLE_DEPLOY.md](ORACLE_DEPLOY.md) detalha backup Neon, migrações,
restauração e validações; ajuste os nomes dos arquivos Compose e volumes para
esta arquitetura dividida.

## Estado desta implantação

Em 29/09/2026, duas VMs E2 Micro Always Free foram criadas em São Paulo:
`recepia-e2-micro` (API, IP público `132.226.243.173`, privado
`10.80.1.67`) e `recepia-e2-evolution` (Evolution, IP público
`163.176.75.140`, privado `10.80.1.122`). O endereço público temporário
é `https://recepia.132-226-243-173.sslip.io`. O acesso HTTPS ao painel,
`/health`, `/ready`, a conexão Neon, os webhooks com token, a Evolution,
o worker e a reinicialização automática de ambas as VMs foram verificados.
As portas 8000, 8080 e 5432 não estão publicadas na Internet.

Uma instância Evolution foi criada para a empresa existente e seu webhook foi
configurado. O status real está **aguardando QR**; a flag antiga de conectado
no Neon foi corrigida para desconectado antes de iniciar o worker. Falta
escanear o QR no painel e validar envio, recebimento e IA com um telefone real.
Após a conexão, repita o reboot da VM Evolution para confirmar a persistência
da sessão autenticada.

O backup Neon anterior à adição das colunas `clinicas.campos_extras` e
`agendamentos.campos_extras` foi criado e validado com `pg_restore --list`.
As duas colunas foram adicionadas em uma transação; nenhuma linha foi removida.
Antes de abrir a aplicação para clientes, considere rotacionar credenciais de
desenvolvimento do Neon e OpenRouter e substituir o hostname temporário por
um domínio próprio quando disponível.
