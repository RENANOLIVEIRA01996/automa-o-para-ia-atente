# Auditoria do vídeo institucional

Auditoria realizada antes das alterações para o tour do aplicativo.

| Ponto | Situação encontrada |
|---|---|
| Recebimento WhatsApp | `api/webhooks.py` autentica o webhook, resolve a empresa pela instância e ignora mensagens próprias, grupos e duplicatas. `services/ai/inbound.py` grava cliente, conversa e mensagem antes de chamar a IA. |
| Evolution/Baileys | `services/whatsapp.py` cria a instância com `WHATSAPP-BAILEYS`; produção fixa Evolution v2.3.7 nos Compose. |
| Texto de saída | `WhatsAppService.enviar_mensagem` chama `POST /message/sendText/{instance}`; `inbound.py` e `api/conversas.py` são os principais chamadores. |
| Mídia de saída | Antes desta mudança não havia envio de vídeo, imagem, documento, URL ou arquivo. Uploads clínicos são outro fluxo, privado, sem compartilhamento público. |
| Configuração por empresa | `Clinica` e `ConfiguracaoNegocio` guardam tipo de negócio, descrição, instruções da IA e regras; API em `api/negocio.py`. |
| Prompt | `services/ai/agent.py` monta o prompt com dados filtrados por `clinica_id`. O tenant interno `RECEPIA` possui prompt comercial próprio. |
| Intenções e tools | A IA seleciona tools tipadas em `services/ai/tools.py`; só as permitidas ao segmento são expostas. O fluxo comercial também encaminha intenção explícita de compra a humano. |
| Diretórios públicos | `dashboard/` é montado como estático; landing e CSS são servidos por rotas específicas em `main.py`. Não havia `/media`. |
| Domínio público | `Caddyfile.production` usa `DOMAIN` e HTTPS. `PUBLIC_WEBHOOK_URL` no Compose dividido é interno e não serve para baixar mídia. `APP_URL` existe, mas pode estar ausente no ambiente. |
| Servir arquivos | FastAPI usa `StaticFiles` no painel e `FileResponse` em landing/CSS. O vídeo será servido por uma rota fixa para um único MP4. |
| Logs e erros | `recepia.inbound`, `recepia.agent` e webhook já registram falhas sem mostrar erro técnico ao cliente. O novo envio registra status da Evolution sem gravar token ou conteúdo do retorno. |
| Isolamento | Instância, conversa, cliente e mensagens têm `clinica_id`. A tool oficial fica restrita a `tipo_negocio=RECEPIA`; a mídia oficial é pública e não contém dados privados de empresas. |

O contrato `POST /message/sendMedia/{instance}` da Evolution aceita `mediatype=video`, `media` por URL e `caption` (código oficial: [rota](https://github.com/evolution-foundation/evolution-api/blob/main/src/api/routes/sendMessage.router.ts), [controller](https://github.com/evolution-foundation/evolution-api/blob/main/src/api/controllers/sendMessage.controller.ts)).

## Captura do tour

As telas em `assets/screenshots/` foram capturadas de uma instância local do próprio Recepia, usando uma base SQLite isolada e dados de demonstração. Nenhum dado de cliente ou credencial de produção foi utilizado. O vídeo identifica as telas como demonstração.
