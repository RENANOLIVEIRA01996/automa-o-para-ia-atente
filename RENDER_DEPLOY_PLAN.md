# Plano atual: teste gratuito no Render

## Motivo da alteração

O primeiro Blueprint preparava API, Evolution privada, worker e discos persistentes em planos pagos. A tela do Render pediu cartão, e o usuário solicitou retirar essa exigência. O `render.yaml` da raiz agora contém apenas um Web Service com `plan: free`, sem disco e sem serviços pagos. O desenho anterior permanece no histórico Git, sem ser aplicado.

## Escopo funcional do Free

- Painel e API FastAPI públicos, com tabelas persistentes no Neon existente.
- OpenRouter configurado por variáveis no Render, sem chaves no repositório.
- Sem migração automática do Neon no boot. `/health` verifica o processo; `/ready` verifica o banco.
- Sem Evolution hospedada, sem worker de lembretes e sem persistência de arquivos locais. Os uploads são bloqueados por `FILE_UPLOADS_ENABLED=false` para não gravar dados que sumiriam quando o serviço hibernasse.
- É possível configurar depois uma Evolution externa por `EVOLUTION_API_URL` e `EVOLUTION_API_KEY`, mas a API Free hiberna e não garante resposta WhatsApp contínua.

## Limites e validação

O Render documenta que o Free hiberna após 15 minutos sem tráfego, perde arquivos locais em reinícios e não aceita disco persistente: [Deploy for Free](https://render.com/docs/free). Blueprints pedem `sync: false` na criação inicial e `plan: free` é válido para Web Services: [Blueprint YAML Reference](https://render.com/docs/blueprint-spec).

Validar o esquema oficial do `render.yaml`, os testes e o build Docker antes do push. Não criar serviços nem alterar o Neon automaticamente. Após o push, o usuário deve atualizar a tela do Render, conferir a prévia de um único serviço Free e decidir quando iniciar o primeiro deploy.
