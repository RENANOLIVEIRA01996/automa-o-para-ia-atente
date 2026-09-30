# Recepia na Oracle Cloud: Ubuntu 24.04 ARM64

Este guia executa a arquitetura existente em uma VM 24/7. Dados de empresas,
agendamentos, conversas e IA permanecem no **Neon PostgreSQL**. A Evolution API
usa um PostgreSQL **privado da VM** para seus metadados e o volume
`recepia_evolution_data` para arquivos das sessões Baileys. Os dois precisam ser
preservados juntos. O OpenRouter continua como provedor de IA. Não há Redis:
o cache local da Evolution é mantido como no Compose atual.

O Compose de produção publica somente **80/tcp, 443/tcp e 443/udp** pelo Caddy.
API (8000), Evolution (8080) e PostgreSQL (5432) não têm portas publicadas.
O Caddy emite e renova HTTPS automaticamente quando o DNS aponta para a VM.

## Limite de custo deste projeto

Na região principal `sa-saopaulo-1`, use **uma única** VM
`VM.Standard.A1.Flex` com no máximo **2 OCPUs e 8 GiB de RAM** e volume de boot
de **50 GiB**. Isso fica dentro da franquia Always Free de 2 OCPUs, 12 GiB
e 200 GiB de armazenamento total; consulte o uso total da conta antes de criar
outros recursos. Não escolha outra shape, balanceador, NAT Gateway, disco extra
ou região como alternativa automática quando faltar capacidade A1. As VMs
Always Free só são gratuitas na região principal da conta; nesta conta, ela é
São Paulo. As três zonas de falha da única zona de disponibilidade de São Paulo
foram consultadas e todas estavam sem capacidade A1 em 29/09/2026. A Oracle
pode responder `OUT_OF_HOST_CAPACITY`; nesse caso, aguarde capacidade e tente
novamente. O limite de serviço mostrado pela API pode ser maior que a franquia
gratuita, por isso não serve como teto de custo. Monitore também saída de dados,
armazenamento e qualquer outro produto usado fora deste Compose.

Em 29/09/2026, a rede `recepia-vcn` foi preparada na conta, mas a tentativa de
criar a VM A1 falhou por falta de capacidade em São Paulo. Confirme o inventário
da conta antes de repetir a criação; não crie uma segunda VM se a primeira já
existir.

## 1. Preparar Ubuntu e rede

Crie uma VM **Ubuntu 24.04 ARM64** com IP público estável e disco persistente.
Para carga leve, planeje 4 GiB de RAM ou mais e pelo menos 2 vCPU; várias
sessões WhatsApp exigem medição e possível aumento. Separe espaço para imagens,
dados e backups (por exemplo, 30 GiB ou mais, conforme retenção). Ative tráfego
de saída para Neon, OpenRouter, WhatsApp, Docker Hub e ACME.

Na VCN da Oracle, libere entrada **22/tcp apenas do seu IP**, **80/tcp** e
**443/tcp**; **443/udp** é opcional para HTTP/3. Não libere 5432, 8000, 8080 ou
2019. Se houver firewall no Ubuntu, aplique as mesmas regras nele. Configure o
registro DNS **A** do domínio escolhido para o IP da VM antes de iniciar o Caddy.
Se usar IPv6/AAAA, configure-o corretamente ou remova o registro AAAA.

## 2. Conectar por SSH

No seu computador, use a chave privada fornecida ou registrada ao criar a VM:

```bash
ssh -i /caminho/da/sua-chave.key ubuntu@IP_PUBLICO_DA_VM
```

O usuário padrão de uma imagem Ubuntu da Oracle costuma ser `ubuntu`. Guarde a
chave privada fora do repositório e limite suas permissões de arquivo.

## 3. Instalar dependências

Uma VM nova precisa de Git para obter o script. O script instala OpenSSL, Docker
Engine, CLI, Buildx e Compose Plugin pelo repositório oficial do Docker; não adiciona o
usuário ao grupo `docker` (esse grupo equivale a acesso root).

```bash
sudo apt-get update
sudo apt-get install -y git
```

## 4. Clonar o projeto

Use a URL do repositório autorizado para sua instalação:

```bash
git clone URL_DO_REPOSITORIO recepia-source
cd recepia-source/recepia
sudo bash scripts/oracle-setup.sh
sudo docker compose version
```

Se o clone tiver outra estrutura, entre na pasta que contém
`docker-compose.production.yml`. O script é idempotente em Ubuntu 24.04 ARM64.

## 5. Configurar `.env`

```bash
umask 077
cp .env.production.example .env
chmod 600 .env
nano .env
```

Preencha `DATABASE_URL` com a URL **direta** do Neon, contendo TLS
(`sslmode=require`); confirme que o banco é o mesmo usado hoje. Use a URL direta
também para a preparação do esquema. Ajuste `DOMAIN`, `APP_URL` e
`ALLOWED_ORIGINS` ao domínio com HTTPS. Para múltiplas origens permitidas,
separe-as por vírgulas sem `*`.

Gere **valores distintos** para `JWT_SECRET`, `ADMIN_API_KEY`,
`EVOLUTION_API_KEY`, `EVOLUTION_WEBHOOK_SECRET` e `POSTGRES_PASSWORD` com
`openssl rand -hex 32`. A senha hexadecimal do PostgreSQL local é compatível
com a URI de conexão da Evolution sem codificação adicional. Defina
`OPENROUTER_API_KEY` e `OPENROUTER_MODEL` com um modelo que suporte ferramentas;
`OPENROUTER_FALLBACK_MODEL` é opcional. Para continuar o atendimento quando
o OpenRouter atingir o limite, configure também `GROQ_API_KEY`; o agente usa
`GROQ_FALLBACK_MODEL=openai/gpt-oss-20b` no Groq. A chave precisa estar no
`.env` da VM API e o contêiner precisa ser recriado após a alteração. Não cole
os valores em documentação, comandos de chat ou Git.

`PUBLIC_WEBHOOK_URL=http://api:8000` é **interno**: cada instância da Evolution
envia os callbacks diretamente à API dentro da rede Docker. O navegador usa
`APP_URL=https://...`. O Compose fixa `DEBUG=false`, OpenRouter, endereço da
Evolution e migrações automáticas desligadas. Sem `GROQ_API_KEY`, o caminho
OpenRouter continua funcionando sem fallback entre provedores.

Antes de expor a aplicação, avalie a rotação das chaves usadas no desenvolvimento,
principalmente se foram compartilhadas. Rotacione com cuidado: trocar
`JWT_SECRET` invalida sessões do painel; trocar a chave da Evolution requer
igualar o valor no Compose e API; trocar o segredo do webhook exige reconfigurar
os webhooks das instâncias existentes. **Não troque `POSTGRES_PASSWORD` apenas no
`.env` se o volume PostgreSQL já existir**: a senha gravada no banco não muda
automaticamente. Não copie `.env` para backups públicos.

## 6. Iniciar os serviços

Verifique o Compose sem imprimir a configuração completa, pois ela inclui
segredos interpolados:

```bash
sudo docker compose -f docker-compose.production.yml config --quiet
sudo docker compose -f docker-compose.production.yml build api worker
sudo docker compose -f docker-compose.production.yml up -d postgres evolution
```

Para um Neon **novo** ou após ensaiar em uma branch e fazer backup do Neon
existente, prepare o esquema uma vez. `RUN_DB_MIGRATIONS_ON_STARTUP=false` evita
alterações automáticas no banco durante reinícios e atualizações:

```bash
sudo docker compose -f docker-compose.production.yml run --rm --no-deps api \
  python scripts/prepare_database.py --apply
sudo docker compose -f docker-compose.production.yml up -d
```

Nunca rode o `docker-compose.yml` de desenvolvimento em paralelo com o de
produção no mesmo diretório: eles podem usar o mesmo nome de projeto e volumes.
Não execute `docker compose down -v` em produção.

## 7. Verificar healthchecks

```bash
sudo docker compose -f docker-compose.production.yml ps
sudo docker compose -f docker-compose.production.yml exec -T api \
  curl -fsS http://127.0.0.1:8000/health
sudo docker compose -f docker-compose.production.yml exec -T api \
  curl -fsS http://127.0.0.1:8000/ready
curl -fsS https://SEU_DOMINIO/health
```

`/health` confirma o processo; `/ready` faz `SELECT 1` no Neon. PostgreSQL,
Evolution e API têm healthchecks. O worker APScheduler não expõe HTTP; confirme
seu processo em `ps` e a linha `Recepia scheduler iniciado` nos logs. Um estado
`unhealthy` não reinicia contêineres sozinho: examine os logs e a causa.

## 8. Verificar logs

```bash
sudo docker compose -f docker-compose.production.yml logs --tail=100 api
sudo docker compose -f docker-compose.production.yml logs --tail=100 worker
sudo docker compose -f docker-compose.production.yml logs --tail=100 evolution
sudo docker compose -f docker-compose.production.yml logs --tail=100 caddy
```

Todos os serviços usam log Docker `json-file` com rotação de 10 MiB × 3 arquivos.
Logs ainda podem conter dados pessoais de mensagens ou erros; restrinja acesso
a quem opera a VM. Não publique saídas completas de `docker compose config`,
`docker inspect` ou `env`, que podem incluir credenciais.

## 9. Conectar WhatsApp

Abra `https://SEU_DOMINIO/dashboard/saas.html`, autentique-se na empresa e use
**WhatsApp → Conectar WhatsApp**. O QR Code é produzido pela Evolution. Cada
empresa conserva sua instância própria, identificada pelo nome no webhook.
Confirme `GET /api/whatsapp/status` pelo painel e envie uma mensagem de teste
ao número vinculado. Verifique resposta da IA e um agendamento de teste. O
webhook usa `X-Webhook-Token` validado pela API.

Na migração de outra máquina, **restaure primeiro** o dump do banco da Evolution
e o volume `evolution_data` antes de conectar ou criar instâncias nesta VM.
Copiar somente o QR Code ou somente o banco não preserva a sessão. Se já houver
instâncias com URL de webhook antiga, confira a contagem e depois aplique a
atualização do callback interno:

```bash
sudo docker compose -f docker-compose.production.yml exec -T api \
  python scripts/sync_evolution_webhooks.py
sudo docker compose -f docker-compose.production.yml exec -T api \
  python scripts/sync_evolution_webhooks.py --apply
```

## 10. Testar persistência da sessão

Depois de conectar, anote o estado no painel e execute:

```bash
sudo docker compose -f docker-compose.production.yml restart evolution
sudo docker compose -f docker-compose.production.yml ps
```

Espere a Evolution ficar saudável e confirme que o painel mostra a instância
conectada **sem novo QR Code**. Envie e receba outra mensagem. Se pedir novo QR,
inspecione logs e confira **ambos** `recepia_postgres_data` e
`recepia_evolution_data`; não apague volumes para tentar corrigir.

## 11. Reiniciar a VM

Em janela de manutenção, após teste e backup:

```bash
sudo reboot
```

Conecte novamente por SSH após a reinicialização.

## 12. Confirmar inicialização automática

```bash
sudo systemctl is-enabled docker
sudo systemctl is-active docker
cd ~/recepia-source/recepia
sudo docker compose -f docker-compose.production.yml ps
curl -fsS https://SEU_DOMINIO/health
```

Docker e containerd ficam habilitados no boot; cada serviço usa
`restart: unless-stopped`. Não é necessário criar um serviço systemd adicional
para o Compose. Verifique novamente WhatsApp, webhook e agendamentos.

## 13. Backup

Faça backups periódicos **fora da VM** e teste a restauração. Uma branch/snapshot
do Neon é útil, mas mantenha também um dump exportável. Use um cliente `pg_dump`
da mesma versão principal do servidor Neon ou mais novo. No exemplo abaixo,
ajuste `PG_MAJOR` para a versão do seu Neon. Pare os serviços que escrevem antes
do backup consistente entre o banco da Evolution e a sessão:

```bash
cd ~/recepia-source/recepia
umask 077
mkdir -p backups
PG_MAJOR=16  # ajuste conforme a versão PostgreSQL do Neon
sudo docker compose -f docker-compose.production.yml stop caddy api worker evolution
sudo docker run --rm --env-file .env postgres:${PG_MAJOR}-alpine sh -ec \
  'pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --no-acl' \
  > backups/recepia-neon.dump
sudo docker compose -f docker-compose.production.yml exec -T postgres \
  pg_dump -U recepia -Fc evolution > backups/evolution.dump
for volume in evolution_data recepia_fotos recepia_avatares recepia_logos caddy_data caddy_config; do
  sudo docker run --rm -v "recepia_${volume}:/data:ro" \
    -v "$PWD/backups:/backup" alpine:3.20 \
    tar -C /data -czf "/backup/${volume}.tar.gz" .
done
sudo chown -R "$(id -u):$(id -g)" backups
chmod 700 backups
chmod 600 backups/*
sudo docker compose -f docker-compose.production.yml up -d
```

Guarde também, em cofre separado, a versão de produção do `.env` e a referência
do commit implantado. `backups/` deve permanecer fora do Git (veja `.gitignore`).
Transfira os arquivos para armazenamento seguro fora da VM com `scp`/SFTP ou
ferramenta de backup de sua escolha; limite acesso, cifre e defina retenção.
O dump do Neon contém dados de todas as empresas. O dump e volume da Evolution
podem conter dados e material de sessão do WhatsApp.

## 14. Restauração

Ensaie primeiro em VM e branch/banco Neon de teste. A restauração sobre produção
substitui dados: pare Caddy, API, worker e Evolution, confirme o destino e faça
um backup atual antes. Configure no `.env` a URL do **banco Neon de destino**;
use `PG_MAJOR` compatível. Traga os arquivos de backup para `backups/`.

```bash
cd ~/recepia-source/recepia
PG_MAJOR=16  # ajuste conforme a versão PostgreSQL do Neon
sudo docker compose -f docker-compose.production.yml stop caddy api worker evolution
sudo docker compose -f docker-compose.production.yml up -d postgres
sudo docker run --rm --env-file .env -v "$PWD/backups:/backup:ro" \
  postgres:${PG_MAJOR}-alpine sh -ec \
  'pg_restore --dbname="$DATABASE_URL" --clean --if-exists --no-owner --no-acl /backup/recepia-neon.dump'
sudo docker compose -f docker-compose.production.yml exec -T postgres \
  pg_restore -U recepia -d evolution --clean --if-exists --no-owner \
  < backups/evolution.dump
for volume in evolution_data recepia_fotos recepia_avatares recepia_logos caddy_data caddy_config; do
  sudo docker volume create "recepia_${volume}" >/dev/null
  sudo docker run --rm -v "recepia_${volume}:/data" \
    -v "$PWD/backups:/backup:ro" alpine:3.20 \
    tar -C /data -xzf "/backup/${volume}.tar.gz"
done
sudo docker compose -f docker-compose.production.yml up -d
```

Restaure os arquivos em volumes **vazios** quando estiver em outra VM. Em volume
existente, extração por cima não remove arquivos antigos. Confira `/ready`,
o status das instâncias, uma mensagem e um agendamento após restaurar.

## 15. Atualização

Faça backup e ensaio em uma branch Neon. Anote o commit atual. Reveja mudanças
de esquema e o changelog da Evolution antes de alterar sua tag fixa; novas
versões podem mudar payload de webhook ou armazenamento de sessão.

```bash
cd ~/recepia-source/recepia
git status --short
git pull --ff-only
sudo docker compose -f docker-compose.production.yml config --quiet
sudo docker compose -f docker-compose.production.yml build api worker
sudo docker compose -f docker-compose.production.yml stop caddy api worker
```

Se a versão exigir migração, **após backup e ensaio**, execute agora:

```bash
sudo docker compose -f docker-compose.production.yml run --rm --no-deps api \
  python scripts/prepare_database.py --apply
```

Finalize a atualização:

```bash
sudo docker compose -f docker-compose.production.yml up -d
sudo docker compose -f docker-compose.production.yml ps
```

Se a atualização falhar, volte ao commit anterior e restaure o banco somente
se a migração o alterou. `git pull` não deve incluir `.env`.

## 16. HTTPS e domínio

Use um domínio ou subdomínio dedicado, por exemplo `app.seudominio.com`, com
registro A para o IP público estável da VM. No `.env`, use
`DOMAIN=app.seudominio.com`, `APP_URL=https://app.seudominio.com` e
`ALLOWED_ORIGINS=https://app.seudominio.com`. Abra 80/tcp e 443/tcp na VCN e no
firewall local; o Caddy precisa de ambos para emissão/renovação de certificado e
redirecionamento HTTP → HTTPS. 443/udp habilita HTTP/3, se desejar.

Enquanto não houver domínio próprio, é possível usar gratuitamente um nome
temporário de [sslip.io](https://sslip.io/), por exemplo
`recepia.203-0-113-10.sslip.io` para o IP `203.0.113.10`. Verifique a resolução
DNS antes de iniciar o Caddy. Configure `DOMAIN` com esse nome e `APP_URL` e
`ALLOWED_ORIGINS` com `https://` seguido dele. O certificado HTTPS pode ser
emitido pelo Caddy, mas a disponibilidade do nome depende de um serviço DNS de
terceiros. Se o IP público mudar, atualize o nome e as variáveis. Evite divulgar
esse endereço como identidade definitiva da empresa.

Se o domínio atual ainda apontar para Render ou para o splash antigo, ajuste DNS
e redirecionamentos de forma coordenada. Os caminhos do frontend usam a mesma
origem da API, então não é necessário publicar a porta 8000. O callback da
Evolution permanece interno em `http://api:8000`; acesso externo ao webhook,
se houver, passa por HTTPS e continua exigindo o token. Teste:

```bash
curl -I https://SEU_DOMINIO/
curl -fsS https://SEU_DOMINIO/health
```

## Limites conhecidos

- Uma única VM é ponto único de falha. `restart: unless-stopped` cobre reboot e
  saída de processos, mas não indisponibilidade da Oracle, Neon, OpenRouter ou
  WhatsApp.
- O worker de agenda é único. Não suba duas cópias: elas poderiam enviar
  confirmações e lembretes duplicados.
- `Dockerfile` usa `python:3.12-slim`; Evolution `v2.3.7` e PostgreSQL 16 têm
  imagens ARM64. O build real e o handshake WhatsApp devem ser verificados na VM.
- Limites de CPU, RAM e conexões do Neon dependem da quantidade de empresas e
  mensagens. Acompanhe `sudo docker stats`, uso de disco e logs após a migração.
