# Plano da interface por segmento

## Auditoria (27/09/2026)

- Frontend estático, sem React/TypeScript: `dashboard/index.html` contém o painel legado e login; `dashboard/saas.html` contém o painel SaaS genérico. A sidebar e os cards de `saas.html` eram fixos.
- `landing/cadastro.html` grava `tipo_negocio` no cadastro. O login em `/dashboard/` redireciona para `/dashboard/saas.html`; a interface clínica anterior permanece em `?legacy=1`.
- `Clinica` é o tenant e persiste `tipo_negocio`. `Paciente`, `Procedimento` e `Agendamento` já funcionam como cliente, serviço e agendamento, com nomes físicos preservados por compatibilidade. `Paciente.campos_extras` já é JSON.
- `database.py` usa `create_all` e `ALTER TABLE ... IF NOT EXISTS` para migrações idempotentes em PostgreSQL; não há Alembic. Toda tabela/coluna nova deve ser aditiva e ter `clinica_id`.
- A API `/api/negocio/indicadores` fornece contagens genéricas. Métricas como receita, lavagens em andamento e quartos ocupados exigem consultas novas; não devem ser exibidas com valores inventados.
- `api/procedimentos.py` já guarda preço, descrição, duração em minutos e ativo, mas o DELETE apaga fisicamente. A agenda e a IA dependem do mesmo catálogo.
- O painel legado contém prontuário, odontograma e muitos textos clínicos. O painel SaaS será o núcleo compartilhado de todos os segmentos; as funções clínicas legadas continuam acessíveis somente para tenants clínicos enquanto são integradas ao núcleo.

## Fonte única dos presets

`core/segments.py` guarda nomes, navegação, cards, módulos extras, campos extras, onboarding, ícones e instruções da IA e expõe `get_segment_config`. A API entrega o preset resolvido ao painel; o browser não mantém uma segunda lista de regras.

## Sequência

1. Configuração central para os dez segmentos, com fallback OTHER e testes.
2. Sidebar, títulos, labels e onboarding gerados pelo preset do tenant, sem duplicar páginas.
3. Indicadores reais por segmento e cards reutilizáveis; consultas agregadas preservam isolamento por `clinica_id`.
4. Serviços: unidade visual em minutos/horas, validação, listagem, ativação e exclusão segura com histórico preservado.
5. CAR_WASH completo: veículos vinculados ao cliente e ao agendamento, API, painel e agenda.
6. Presets dos demais segmentos; entidades próprias apenas quando necessárias (ordem de serviço, pet, quarto/reserva).
7. IA recebe o mesmo preset e o contexto real da empresa; ferramentas existentes continuam únicas.
8. Ajustes de navegação, acessibilidade e responsividade; regressão do painel clínico.

## Dados e migração

- Não renomear as tabelas existentes. `procedimentos` continuam sendo serviços, `pacientes` clientes, `agendamentos` agendamentos.
- Usar JSON validado para campos ocasionais e tabelas com `clinica_id` para entidades recorrentes.
- Soft delete para serviços com referências; nunca apagar histórico de agendamentos. A API de novos agendamentos usa somente serviços ativos.
- Aplicar migrações aditivas após testes locais; revisar impacto no banco remoto antes de subir nova versão.

## Verificação

Rodar `ruff check .`, `pytest -q`, checagem de sintaxe JavaScript e testes de navegação dos segmentos. Como não há projeto TypeScript, não há `tsc` aplicável. Exercitar CAR_WASH, CLINIC, BARBERSHOP, 1,5 hora e exclusão com histórico.

## Estado da implementação

- Fonte central, API de preset, navegação e cards dinâmicos: implementados.
- Serviços com edição de duração em horas/minutos e exclusão lógica: implementados.
- CAR_WASH: veículo, agenda vinculada, indicadores, cliente, conversa e drawer de agendamento implementados.
- Presets dos demais segmentos: nomes, títulos, cards, navegação e instruções da IA disponíveis. Pets, ordens de serviço, quartos, reservas, check-in e check-out têm tabelas, API isolada por tenant e telas no mesmo painel.
- PET vincula agendamentos ao pet do tutor; AUTO_REPAIR acompanha ordens e status; HOTEL impede sobreposição de reservas de um quarto e deriva ocupação de reservas ativas. A IA oferece ferramentas específicas para veículos, pets e reservas conforme o segmento.
- Campos ocasionais de cliente, agendamento e empresa usam `campos_extras` JSON, com chaves validadas pelo preset. CONSULTING demonstra os três níveis: empresa do cliente, assunto da reunião e área de atuação. Veículos, pets e quartos continuam em tabelas próprias.
- Métrica monetária usa `agendamentos.valor_previsto`, fotografado no momento da reserva (dados legados usam preço vigente como fallback). Não registra pagamento; a interface chama o indicador de valor estimado.
- `ruff check .` já encontrava 541 avisos de estilo no repositório (principalmente `B008` e `E501`); a verificação `ruff --select F` nos arquivos da refatoração passa. Não há pipeline TypeScript.
- Suíte completa após os campos JSON: 295 testes passaram em 28/09/2026. O smoke JavaScript valida sintaxe, navegação CAR_WASH/PET e duração 1,5 h = 90 min. Os novos testes exercitam isolamento de tenant, vínculo de pet, ordem de oficina, conflito de reservas e persistência de campos adicionais.
- API e worker locais foram reconstruídos. `/health` responde `ok` com banco `ok`; o catálogo retorna 10 segmentos e as tabelas `pets`, `ordens_servico`, `quartos`, `reservas_hotel` e os vínculos de agendamento foram confirmados no banco configurado.
- A chave OpenRouter configurada foi validada pelo endpoint de leitura `/api/v1/key` (HTTP 200, conta free tier); modelos principal e fallback configurados usam `:free`. Nenhuma chamada de inferência paga foi feita nessa verificação. O plano da conta Neon não é inferível pela URL do banco.
