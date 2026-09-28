# Plano de migração para SaaS multissegmento

## Auditoria da base (fase 0)

- Stack real: FastAPI, SQLAlchemy 2, PostgreSQL, dashboard HTML/JavaScript, Docker Compose, Evolution API, Groq e APScheduler. Não há Next.js nem Prisma; manter a stack evita reescrita.
- `clinicas` já é a raiz do tenant. `usuarios` tem `clinica_id` e email único por empresa. JWT é confrontado com o banco em `core/deps.py`; as rotas de pacientes, profissionais, procedimentos e agendamentos filtram por `clinica_id`.
- `pacientes`, `profissionais`, `procedimentos`, `horarios_funcionamento`, `bloqueios_agenda` e `agendamentos` já cobrem grande parte do domínio genérico. Prontuário, odontograma e documentos são módulos clínicos opcionais que devem permanecer para clientes existentes.
- Agenda principal já usa o banco. `services/slots.py` calcula slots, mas está preso ao fuso de São Paulo e não seleciona serviço/profissional. Agendamentos guardam serviço como texto; um índice parcial só protege slots sem profissional na mesma hora, não intervalos sobrepostos.
- Cada `clinica` tem uma instância Evolution. O webhook valida token, descarta grupos e mensagens próprias, e verifica IDs de mensagens. Falta uma tabela de conversas e idempotência com constraint por instância.
- IA atual classifica intenções com Groq e fallback regex. Não há agente genérico com ferramentas, OpenRouter nem custo por tenant persistido.
- Migração existente é SQL idempotente em `database.py` durante o boot; não há histórico Alembic versionado apesar da dependência. `create_all` cria tabelas novas, enquanto colunas de tabelas antigas precisam de `ALTER TABLE`. Cópia de segurança e ensaio em staging são necessários antes de aplicar em produção.
- Docker Compose já contém API, worker, PostgreSQL e Evolution. O dashboard e landing são arquivos estáticos; não há necessidade de serviço frontend adicional.

## Estratégia

1. **Fase 1 — domínio:** manter nomes físicos (`clinicas`, `pacientes`, `procedimentos`) e chaves existentes, expor nomes genéricos na API. Adicionar metadados de empresa, configurações comerciais, preço/descrição do serviço, telefone do profissional e referência opcional do agendamento ao serviço. Migrar com adições nullable ou defaults; não renomear tabelas nem apagar colunas clínicas.
2. **Fase 2 — agenda:** motor com timezone do tenant, duração do serviço, horários por profissional, bloqueios e verificação transacional de conflitos. Criar constraint PostgreSQL para impedir sobreposição, depois de auditar e corrigir conflitos históricos.
3. **Fase 3 — IA:** interface de provider, OpenRouter configurável, timeout, fallback apenas para falha transitória e registro de uso por tenant.
4. **Fase 4 — agente:** ferramentas tipadas e autorizadas pelo tenant, memória recente isolada, confirmação somente após escrita bem-sucedida.
5. **Fase 5 — Evolution:** persistir instâncias e mensagens com unique `(instance, external_message_id)`, proteger webhook e correlacionar tenant pela instância.
6. **Fase 6 — conversas:** tabela de conversas, mensagens e `human_takeover`, com tela e rotas reais.
7. **Fases 7–8:** onboarding genérico, dashboard e agenda responsivos com dados reais.
8. **Fase 9:** testes de isolamento, concorrência, webhook, IA e documentação operacional.

## Riscos e verificações

- O `especialidade` atual determina validação de paciente e documentos. Negócios não clínicos precisam usar uma opção genérica sem quebrar perfis clínicos existentes.
- O índice de slot existente não impede agendamentos com duração maior ou profissional definido. Não anunciar proteção completa contra double booking até implementar a constraint e a checagem transacional.
- Login com email em várias empresas exige escolha explícita do tenant; avaliar o fluxo antes de criar `TenantUser` separado.
- A chave Evolution, a chave OpenRouter e o segredo do webhook ficam apenas no backend.
- Após cada etapa: `ruff check`, compilação Python e `pytest` com APIs externas simuladas. Validação de migração PostgreSQL precisa de banco de staging e backup; SQLite dos testes não prova a migração SQL.

## Estado da implementação

- Fases 1 a 6: entidades comerciais, agenda transacional, OpenRouter, ferramentas do agente, webhook por instância e conversas persistidas implementados. Nomes físicos legados foram preservados.
- Fase 7: cadastro genérico e presets de segmento implementados; fluxo guiado completo de onboarding ainda pendente.
- Fase 8: painel comercial com indicadores, agenda diária/semanal, bloqueios, clientes, profissionais, jornadas, serviços, empresa, IA, conversas e WhatsApp. O painel legado continua disponível para funções clínicas.
- Fase 9: suíte automatizada e documentação operacional adicionadas. O PostgreSQL fornecido estava vazio e recebeu 24 tabelas; o endpoint `/health` respondeu com banco `ok`.
- Os limites de planos e o bloqueio por trial agora dependem de `SAAS_LIMITS_ENABLED`, desligado por padrão conforme a política comercial solicitada.
- O arquivo `.env` local foi criado a partir das credenciais fornecidas e está ignorado pelo Git. O modelo principal foi ajustado para um modelo cujo tool calling passou em chamada real; modelos gratuitos podem mudar ou limitar requisições.
- Validação ainda pendente: conexão e QR Code em uma Evolution API real, fluxo completo de agendamento pelo WhatsApp em ambiente de homologação, e revisão dos direitos de revenda descritos no README original. A URL Evolution configurada usa o nome interno do container, e o Docker daemon não estava ativo nesta sessão; por isso a autenticação Evolution ainda não foi validada.
