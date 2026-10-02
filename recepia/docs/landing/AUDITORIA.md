# Recepia — auditoria e implementação da landing

Base analisada pelo pacote original: commit `2a66e38170250184bfa6c6611148bfad531f6755` do repositório indicado. A observação original de trabalho local, sem commit, push ou deploy, descrevia a preparação do ZIP. A integração posterior foi autorizada pelo usuário na branch `feature/recepia-landing-premium-v1`, sem deploy ou merge.

## Stack e organização

FastAPI 0.115 / Uvicorn 0.32, Python 3.12 no Docker; SQLAlchemy 2.0, PostgreSQL e Alembic; autenticação JWT, isolamento por empresa; WhatsApp via Evolution API; agentes e ferramentas de IA via OpenRouter/Groq; worker e APScheduler. Frontend estático em HTML, CSS e JavaScript. Não há aplicação React/Next.js ou manifest de dependências Node para o frontend. Lucide e Tailwind compilado aparecem nas interfaces existentes.

Inventário anterior à edição: 106 arquivos Python, 24 HTML, 2 CSS, 26 documentos Markdown e configurações SQL/Docker/deploy. Todos os módulos Python passaram por leitura e análise sintática. A inspeção funcional concentrou-se no entrypoint, rotas públicas, APIs de negócio/conversas/WhatsApp/agendamento, catálogo de segmentos, ferramentas e prompt do agente, configurações, arquitetura de execução e testes. Isso não substitui um pentest, auditoria linha a linha de segurança nem teste das integrações em produção.

- `main.py`: API, middleware, rotas públicas e mounts.
- `landing/`: página inicial, cadastro, login, documentos legais, SEO.
- `dashboard/`: painéis SaaS, clínico e admin.
- `static/`: estilos compartilhados existentes.
- `api/`, `core/`, `services/`, `models.py`: operação e regras de negócio.
- `tests/`: regressões com SQLite isolado e integrações mockadas.
- `public/media/`: vídeo institucional anterior, preservado.

## Rota e compatibilidade

A raiz `/` já serve `landing/index.html`, portanto é o local adequado. Apenas o mount `/assets` foi acrescentado ao entrypoint, limitado ao diretório público `landing/assets`. `/cadastro`, `/entrar`, `/dashboard`, `/dashboard/saas.html`, `/dashboard/admin.html`, APIs e estilos compartilhados foram mantidos. Nenhuma dependência de frontend foi acrescentada.

## Recursos comprovados

- Catálogo de dez segmentos em `core/segments.py`.
- Conexão do WhatsApp via QR Code em `api/whatsapp.py`.
- Configuração do negócio e instruções da IA em `api/negocio.py`.
- Ferramentas de serviços, preços, disponibilidade e criação de agendamento em `services/ai/tools.py`.
- Consulta obrigatória da disponibilidade e confirmação apenas após sucesso no prompt em `services/ai/agent.py`.
- Assumir, responder e devolver conversa em `api/conversas.py`.
- Agenda, clientes, profissionais, serviços e histórico no painel SaaS.
- Execução no servidor, API e worker documentados no Docker/README SaaS.

A demonstração da landing usa dados fictícios e não chama as APIs de atendimento. O cenário de lava-rápido pressupõe veículo cadastrado, explicitado abaixo da demonstração. Hotelaria usa reservas, não o fluxo comum de agendamento.

## Riscos e decisões

1. Estilos compartilhados poderiam alterar os painéis: novos CSS/JS isolados em `/assets`.
2. Vídeo em celular ou conexão lenta: imagem WebP responsiva, zoom CSS leve, sem download do vídeo nesses casos.
3. Movimento e leitura: overlays, controles de pausa e `prefers-reduced-motion`; animações pausam fora de tela e em aba oculta.
4. Nenhuma credencial de banco, WhatsApp ou IA é necessária no frontend. Não há chamadas externas da landing para IA nem mensagens reais.
5. Depoimentos da versão anterior não foram reaproveitados como fatos. A nova página tem template oculto para provas reais, sem contadores comerciais ou clientes inventados.
6. Canonical, sitemap e robots passaram a corresponder ao endereço atual. O cadastro já é `noindex`, por isso saiu do sitemap. Antes de trocar domínio, atualizar metadados e URLs dos documentos legais conforme instruções.
7. O vídeo reaproveitado é um loop cinematográfico de seis segundos. Não representa uma gravação de uma pessoa executando movimentos reais. Uma filmagem ou vídeo gerado com gestos naturais elevará o resultado.
8. Hospedagem, configuração da IA, Evolution API e disponibilidade em produção não foram alteradas ou testadas com credenciais reais.

## Arquivos

Alterados: `main.py`, `landing/index.html`, `landing/robots.txt`, `landing/sitemap.xml`, `landing/README.md`.

Criados: `landing/assets/landing.css`, `landing/assets/landing.js`, `landing/assets/favicon.svg`, duas imagens WebP, loops MP4/WebM, fonte local WOFF2 e licença OFL; `tests/test_landing.py`; documentação em `docs/landing/`.

Resultados e screenshots: consulte `docs/landing/VALIDACAO.md` após a revisão.
