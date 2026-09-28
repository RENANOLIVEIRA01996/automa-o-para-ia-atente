# Recepia SaaS multissegmento

Esta evolução usa a base FastAPI existente. As tabelas `clinicas`, `pacientes` e
`procedimentos` continuam com seus nomes físicos para preservar dados e relações;
na camada comercial representam empresa, cliente e serviço. O login em
`/dashboard/` abre o painel SaaS em `/dashboard/saas.html`; a interface
clínica anterior permanece em `/dashboard/?legacy=1` para clínicas.

## Instalação

```bash
git clone https://github.com/Ewertonslv/recepia.git
cd recepia
cp .env.example .env
```

No `.env`, gere `JWT_SECRET`, `ADMIN_API_KEY`, `EVOLUTION_API_KEY` e
`EVOLUTION_WEBHOOK_SECRET` com valores aleatórios próprios. Defina
`POSTGRES_PASSWORD` e ajuste `DATABASE_URL`. Não envie o `.env` ao Git.
`APP_URL` é a URL da aplicação; `PUBLIC_WEBHOOK_URL` precisa ser uma URL
alcançável pela Evolution API (no Compose, `http://api:8000`).
`SAAS_LIMITS_ENABLED=false` mantém os planos e o trial apenas informativos;
ative a cobrança e os bloqueios somente quando essa política estiver pronta.

```bash
docker compose up -d --build
curl http://localhost:8000/health
```

O Compose existente inicia PostgreSQL, Evolution API, API e worker. O banco da
Evolution é criado por `init-db.sql`. Não há dependência de Google Calendar.
API e worker usam o `DATABASE_URL` do `.env`, inclusive quando aponta para um
PostgreSQL externo; o serviço PostgreSQL do Compose continua necessário para
a Evolution. Defina `POSTGRES_PASSWORD` com um segredo próprio para esse serviço.

Para desenvolvimento sem Docker, inicie PostgreSQL, configure `DATABASE_URL`,
instale `pip install -r requirements.txt`, e rode `uvicorn main:app --reload`.

## Criar usuário e empresa

O cadastro público cria empresa e usuário administrador no mesmo fluxo:

```bash
curl -X POST http://localhost:8000/api/signup \
  -H 'Content-Type: application/json' \
  -d '{"nome_clinica":"Barbearia Exemplo","tipo_negocio":"BARBERSHOP",\
"nome_responsavel":"Dono Exemplo","email":"dono@example.com",\
"telefone":"11999990000","senha":"troque-esta-senha",\
"aceito_termos":true}'
```

O campo `especialidade` é opcional e usa `geral` para negócios não clínicos.
Os presets são `BARBERSHOP`, `BEAUTY`, `CLINIC`, `DENTAL`, `AUTO_REPAIR`,
`CAR_WASH`, `PET`, `HOTEL`, `CONSULTING` e `OTHER`. Um superadministrador
também pode usar `/admin/clinicas` (rota legada). O JWT retornado pelo cadastro
autentica as APIs. O painel existente em `/dashboard/` oferece login. Se o
mesmo email e senha estiverem vinculados a mais de uma empresa, informe o ID
da empresa no login; ele aparece em **Empresa e IA** no painel comercial.

## Configurar empresa, serviço e agenda

Abra `/dashboard/saas.html` após fazer login. O checklist inicial leva à
configuração de endereço, horários, serviços, profissional opcional, IA e
WhatsApp. O painel comercial oferece agenda diária e semanal, cadastro de
clientes, bloqueios, serviços e jornadas por profissional.
Em CAR_WASH e AUTO_REPAIR, cadastre um veículo antes de agendar; em PET,
cadastre o pet do tutor. HOTEL usa reservas e quartos, com consulta de
disponibilidade para impedir reservas sobrepostas. Os menus de ordem de serviço,
pets, quartos, reservas, check-in e check-out aparecem somente nos segmentos
correspondentes.
`/api/agenda/slots?procedimento_id=...&data=AAAA-MM-DD` retorna
horários disponíveis em UTC, calculados com o fuso da empresa. As rotas
`/api/agenda/profissionais/{id}/horarios/{dia}` e
`/api/agenda/profissionais/{id}/servicos` configuram jornadas e serviços dos
profissionais. O endpoint de agendamentos usa `procedimento_id` opcional; quando
informado, a duração cadastrada do serviço prevalece.

## Conectar WhatsApp

No painel comercial, abra **WhatsApp → Conectar WhatsApp** e escaneie o QR Code
real da Evolution. O backend cria e configura uma instância por empresa; a
chave principal da Evolution nunca é enviada ao navegador. A API também oferece
`GET /api/whatsapp/status`, `POST /api/whatsapp/desconectar` e
`POST /api/whatsapp/reconectar`. O webhook aceita apenas o segredo configurado
em `EVOLUTION_WEBHOOK_SECRET` e identifica a empresa pelo nome da instância.

## Configurar OpenRouter e testar agendamento por IA

Adicione ao `.env`:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_FALLBACK_MODEL=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Preencha a chave e nomes de modelos com suporte a ferramentas na sua conta
OpenRouter. A disponibilidade de modelos gratuitos muda; por isso não há modelo
gratuito fixo no código. Consulte a [documentação de tool calling do
OpenRouter](https://openrouter.ai/docs/guides/features/tool-calling) para
selecionar modelos compatíveis. Falhas transitórias acionam duas tentativas
por modelo e depois o fallback; erros de argumento não acionam fallback.

Com serviço, horários e WhatsApp configurados, envie ao número conectado:
“Tem horário amanhã à tarde para corte?”. A IA consulta horários reais. Após
escolher um horário, ela só confirma depois da ferramenta
`createAppointment` gravar no PostgreSQL. As conversas e o uso de IA ficam no
banco. Em **Conversas**, é possível assumir o atendimento e devolver para a IA.

Sem chave/modelo OpenRouter, o webhook mantém o classificador determinístico
legado da base. Isso permite desenvolvimento sem gastar chamadas externas.

## Testes

```bash
pip install -r requirements.txt pytest ruff
ruff check api/negocio.py api/agenda.py api/conversas.py services/ai services/availability.py --select E,F
pytest -q
```

As suítes simulam OpenRouter e Evolution; não consomem APIs reais. A migração
de colunas existentes é idempotente em PostgreSQL durante o boot. Faça backup
e valide em staging antes de aplicar a um banco de produção. A proteção contra
agendamentos simultâneos usa lock transacional por empresa nas rotas novas e
no fluxo legado; escritas SQL externas precisam obedecer à mesma regra.

## Limites atuais

O painel clínico e algumas mensagens legadas ainda usam nomenclatura e fuso
de clínica. O onboarding atual é um checklist; uma jornada interativa completa
e validação com uma Evolution API real continuam pendentes. A URL Evolution do
`.env` local usa o nome interno do container e requer Docker Compose ativo.
O README original declara **All Rights
Reserved** e restringe redistribuição e revenda por terceiros; confirme os
direitos comerciais antes de distribuir ou vender esta base.
