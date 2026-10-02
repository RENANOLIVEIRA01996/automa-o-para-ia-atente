# Site público e SEO do Recepia na Oracle — preparação para revisão

Esta etapa prepara código e instruções. **Não houve deploy, alteração da VM, criação de recurso pago, envio de sitemap ou verificação no Search Console.** A indexação e a posição nos resultados do Google não são garantidas.

## Prévia e validação local

No diretório `recepia`, configure as variáveis locais necessárias conforme `.env.example` e execute:

```powershell
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8766
```

Abra `http://127.0.0.1:8766/`. As prévias capturadas estão em [landing/seo-preview-desktop.png](landing/seo-preview-desktop.png), [landing/seo-preview-mobile.png](landing/seo-preview-mobile.png), [landing/seo-preview-servico-desktop.png](landing/seo-preview-servico-desktop.png) e [landing/seo-preview-servico-mobile.png](landing/seo-preview-servico-mobile.png).

Em 02/10/2026, a suíte completa passou com **328 testes**. O navegador foi conferido em larguras de 320, 390, 768, 1440 e 1920 px sem rolagem horizontal; os assets carregaram sem erro de rede ou console. O vídeo tocou no desktop, não foi solicitado no mobile, o botão de pausa funcionou, a demonstração mudou de cenário e os CTAs chegaram a `/cadastro`. O menu mobile e o espaçamento das páginas de serviço também foram conferidos. Estas verificações locais não substituem a conferência na VM após uma publicação autorizada.

## Estado encontrado em 02/10/2026

- O repositório documenta duas VMs Oracle E2 Micro Always Free: API/worker/Caddy em `132.226.243.173` e Evolution em outra VM. O Compose da API usa Neon externo, volumes persistentes para arquivos, `RUN_DB_MIGRATIONS_ON_STARTUP=false` e Caddy como proxy HTTPS. Nenhuma mudança de esquema ou infraestrutura é exigida por este conjunto de arquivos.
- O [Caddyfile.production](../Caddyfile.production) usa `DOMAIN`, compressão `zstd gzip` e `reverse_proxy api:8000`. O [docker-compose.production.api.yml](../docker-compose.production.api.yml) publica 80/443 no Caddy e mantém a API na rede/porta privada configurada.
- O DNS do hostname temporário `recepia.132-226-243-173.sslip.io` resolveu para `132.226.243.173`. Na primeira tentativa, a porta 443 respondeu à conexão TCP, mas a requisição HTTPS expirou. Na repetição, conexões HTTP e HTTPS falharam imediatamente; a conexão SSH à porta 22 também foi negada antes da autenticação. Portanto **capacidade livre, contêineres, certificado e resposta HTTPS da VM não puderam ser verificados ao vivo**. A documentação antiga registra uma implantação funcional em 29/09/2026, mas não prova o estado atual.

## Páginas e domínio

`PUBLIC_SITE_URL` em `config.py` é a única origem canônica usada pelo HTML público, Open Graph, schema.org, sitemap, robots.txt e links que a IA comercial compartilha. O valor padrão é o hostname `sslip.io` atual. Os botões do site usam `/cadastro` relativo à origem visitada. Para domínio próprio, configure `PUBLIC_SITE_URL=https://seudominio.com.br` no `.env` **da VM**, sem barra final. O valor deve ser HTTPS e não pode conter caminho. Não altere ou publique credenciais.

`DOMAIN`, `APP_URL`, `PUBLIC_BASE_URL` e `ALLOWED_ORIGINS` continuam com papéis próprios no Caddy, na API, no vídeo institucional e no CORS. Ao migrar domínio, alinhe todos ao novo host seguindo [ORACLE_E2_DEPLOY.md](../ORACLE_E2_DEPLOY.md). Isso é uma mudança de operação que precisa ser revisada na VM antes de executá-la. O domínio `sslip.io` é temporário; um domínio próprio dá controle de DNS e da verificação no Google.

Páginas comerciais indexáveis e incluídas em `/sitemap.xml`:

| Rota | Conteúdo |
| --- | --- |
| `/` | Landing premium, visão geral e links para os serviços. |
| `/automacao-whatsapp-empresas` | Conexão, configuração e acompanhamento do WhatsApp. |
| `/atendimento-whatsapp-inteligencia-artificial` | Respostas baseadas no negócio e atendimento humano. |
| `/agendamento-automatico-whatsapp` | Consulta de disponibilidade, confirmação e registro do horário. |

`/termos` e `/privacidade` também estão no sitemap. Não foram criadas páginas específicas por segmento: a landing já apresenta os segmentos, mas o site ainda não tem conteúdo independente suficiente para páginas úteis de cada um. `/cadastro`, `/entrar`, `/dashboard/*`, APIs e rotas administrativas recebem `X-Robots-Tag: noindex, nofollow, noarchive`; cadastro e login também mantêm meta `noindex`. `robots.txt` permite que o crawler veja o `noindex` do cadastro, login e painéis; APIs e rotas administrativas continuam bloqueadas no robots e protegidas pela autenticação. A autenticação e o fluxo de login não foram modificados. [O Google esclarece que bloquear uma URL no robots.txt impede que o crawler leia o `noindex`](https://developers.google.com/search/docs/crawling-indexing/block-indexing).

## Conferência na VM antes de qualquer publicação

Quando o SSH voltar a funcionar, **somente leitura**:

```bash
cd ~/recepia
git status --short
git rev-parse --short HEAD
free -m
df -h /
sudo docker stats --no-stream
sudo docker compose -f docker-compose.production.api.yml ps
sudo docker compose -f docker-compose.production.api.yml config --quiet
curl -fsS http://127.0.0.1:8000/health
curl -fsS https://recepia.132-226-243-173.sslip.io/health
```

Confirme memória e disco suficientes para **um** build da imagem existente, o estado do Caddy/API/worker, certificado válido, HTTPS da raiz e `/health`, e a branch/commit realmente implantados. Não mostre `docker compose config` sem `--quiet`: ele pode revelar variáveis sensíveis. Não execute migrações para esta alteração. Mantenha Evolution e banco sem mudanças.

O endpoint FastAPI `/health` aceita `GET`; `curl -I` usa `HEAD` e retorna 405 mesmo quando a aplicação está saudável. Depois de aprovar o deploy, a atualização deve usar o commit revisado da branch feature, sem merge automático na `main`. Faça backup do estado atual da VM, confira o `git status`, construa a imagem da API/worker já existente e recrie apenas esses serviços pelo Compose. Verifique `/`, as três páginas comerciais, `/cadastro`, `/dashboard/`, `/dashboard/saas.html`, `/dashboard/admin.html`, `/health`, `/ready`, `/robots.txt` e `/sitemap.xml`. Confirme que o `X-Robots-Tag` está ausente das páginas comerciais e presente nas privadas. Só divulgue os links após HTTPS e os CTAs funcionarem no domínio publicado.

## Plano de publicação para aprovação

**Estado atual: aguardar.** O DNS funciona, mas HTTP, HTTPS e SSH não estão acessíveis deste computador. Não é possível conferir capacidade, imagem anterior nem aplicar um rollback testado. Primeiro confirme no painel Oracle que a VM API está em execução e recupere o acesso pela configuração já existente, sem criar recursos. Depois rode a conferência de somente leitura acima. Se o código na VM não for um checkout Git limpo, se o Caddy/API/worker estiverem indisponíveis ou se faltar espaço para a nova imagem e a anterior, interrompa a atualização e investigue antes de trocar qualquer contêiner.

Após aprovação explícita para **commit, push e deploy**, a sequência prevista é:

1. Revisar o diff local e registrar estas alterações na branch `feature/recepia-landing-premium-v1`; enviar essa branch ao GitHub, sem merge na `main`. Anotar o SHA aprovado.
2. Na VM API, verificar que `~/recepia` é o checkout usado pelo Compose, que `git status --porcelain` está vazio e que o `.env` está protegido e contém o domínio atual. Anotar o SHA implantado e o ID da imagem `recepia-api:production`. Não copiar o `.env` para o repositório.
3. Com memória, swap e disco conferidos, dar uma segunda tag à imagem atual para rollback, buscar **o SHA aprovado** da branch e posicionar o checkout nele. O novo código não exige migração ou alteração da VM Evolution. Configurar `PUBLIC_SITE_URL` para a origem HTTPS atual no `.env` da VM se ainda não estiver definido; conservar os demais segredos.
4. Reconstruir a imagem `recepia-api:production` com o Compose existente e recriar `api` e `worker`. O Caddy continua usando o mesmo `DOMAIN` e a mesma configuração. Não recriar a VM, volumes, banco, Evolution ou certificados.
5. Executar os testes de rota e cabeçalhos abaixo no domínio publicado, conferir visual desktop/mobile e logs dos três contêineres. Se houver regressão, restaurar a tag da imagem anterior e o SHA anterior do checkout e recriar `api` e `worker`; conferir `/health`, `/ready`, painel e WhatsApp antes de encerrar.

Com os pré-requisitos confirmados, estes são os comandos previstos **para execução somente após aprovação** na VM API:

```bash
cd ~/recepia
test -z "$(git status --porcelain)" || { echo 'Checkout alterado; pare aqui'; exit 1; }
git rev-parse HEAD                         # guardar como SHA_ANTERIOR
sudo docker image inspect recepia-api:production --format '{{.Id}}'
ROLLBACK_TAG=recepia-api:rollback-seo-v1
if sudo docker image inspect "$ROLLBACK_TAG" >/dev/null 2>&1; then echo 'Tag de rollback já existe; pare aqui'; exit 1; fi
sudo docker tag recepia-api:production "$ROLLBACK_TAG"
git fetch origin feature/recepia-landing-premium-v1
git switch --detach SHA_APROVADO
sudo docker compose -f docker-compose.production.api.yml config --quiet
sudo docker compose -f docker-compose.production.api.yml build api
sudo docker compose -f docker-compose.production.api.yml up -d --no-build api worker
sudo docker compose -f docker-compose.production.api.yml ps
curl -fsS https://recepia.132-226-243-173.sslip.io/health
curl -fsS https://recepia.132-226-243-173.sslip.io/ready
```

Substitua `SHA_APROVADO` pelo SHA revisado; não digite a expressão literalmente. Registre `SHA_ANTERIOR` e `ROLLBACK_TAG` fora da VM para a recuperação. A tag de rollback não pode existir antes da operação e deve ser removida apenas depois de uma janela de observação. Se houver outras mudanças de código ou ambiente na VM, reavalie o plano antes de rodar esses comandos. Para restaurar a imagem anterior, volte primeiro ao `SHA_ANTERIOR`, aplique `sudo docker tag "$ROLLBACK_TAG" recepia-api:production` e use `sudo docker compose -f docker-compose.production.api.yml up -d --no-build --force-recreate api worker`.

Use `curl -fsS -o /dev/null -w '%{http_code}\n' "https://recepia.132-226-243-173.sslip.io/ROTA"` para cada rota pública e privada citada acima. Para examinar os cabeçalhos de uma página, faça GET com `curl -fsS -D - -o /dev/null URL`; HEAD pode responder 405. Inspecione também as URLs e o domínio em `/sitemap.xml`, o conteúdo de `/robots.txt`, o canonical/OG/schema no HTML, e a navegação dos CTAs até `/cadastro`. O Search Console só entra depois da publicação validada e do controle do domínio.

## Apontar domínio próprio

1. Registre ou use um domínio que você controla. Crie um registro DNS **A** para o host público apontando ao IP público confirmado da VM API; aguarde a propagação e confirme a resolução. Escolha uma versão canônica (`www` ou sem `www`).
2. Confira 80/443 na VCN e no firewall local antes de pedir certificado ao Caddy. O Caddy atual atende apenas o host definido em `DOMAIN`; planeje a transição do hostname antigo antes de trocá-lo para não quebrar links já enviados por WhatsApp.
3. Na VM, após revisão e autorização, alinhe `DOMAIN`, `APP_URL`, `PUBLIC_SITE_URL`, `PUBLIC_BASE_URL` e `ALLOWED_ORIGINS` ao novo host. Recrie somente os serviços afetados pelo Compose existente. Não altere os valores de banco, chaves de IA ou Evolution.
4. Teste DNS, certificado HTTPS, redirecionamento HTTP → HTTPS, canonical, Open Graph, sitemap, cadastro, painéis e APIs. Se o host antigo continuar ativo, escolha um redirecionamento permanente após confirmar o novo; o canonical sozinho é uma indicação, não um redirecionamento.

## Google Search Console

Após o site estar publicamente acessível em HTTPS:

1. Em [Google Search Console](https://search.google.com/search-console/), adicione uma propriedade **Domínio** para o domínio próprio. Copie o registro TXT fornecido pelo Google para o DNS e clique em verificar. Uma propriedade de **Prefixo de URL** é alternativa quando você precisa acompanhar apenas uma origem HTTPS; ela aceita outros métodos de verificação. [Instruções oficiais de propriedade e verificação](https://support.google.com/webmasters/answer/34592).
2. Abra `https://SEU_DOMINIO/robots.txt` e `https://SEU_DOMINIO/sitemap.xml`; confirme URLs absolutas do mesmo domínio, HTTP 200 e ausência de páginas privadas no sitemap. No relatório **Sitemaps**, envie `sitemap.xml` e confira o processamento e os erros. [Guia oficial de sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap), [relatório Sitemaps](https://support.google.com/webmasters/answer/7451001).
3. Use **Inspeção de URL** para a raiz e as três páginas comerciais. Teste a URL publicada, veja o canonical escolhido e eventuais bloqueios; solicite indexação se fizer sentido. Repita a conferência após mudanças importantes. [Guia oficial de Inspeção de URL](https://support.google.com/webmasters/answer/9012289).
4. Acompanhe **Indexação > Páginas** e **Desempenho** nas semanas seguintes. Enviar sitemap e pedir indexação ajuda na descoberta, mas [não garante indexação nem classificação](https://developers.google.com/search/docs/fundamentals/how-search-works). Registre a verificação apenas depois de concluí-la na conta do proprietário.
