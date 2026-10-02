# Validação da landing Recepia

## Resultado

Na validação original do pacote, 48 testes passaram: 44 regressões existentes em prontidão de execução, cadastro, autenticação, agente, atendimento humano e segmentos; 4 verificações novas da landing, assets, isolamento de diretório, preservação de rotas, CTAs e SEO. O smoke de JavaScript do dashboard existente também passou. Nenhuma integração de produção foi chamada.

Revisão realizada com FastAPI/Uvicorn local e Chromium headless. Screenshots mobile simulam viewport e toque; não representam teste em um iPhone físico ou Safari real.

## Integração no repositório (02/10/2026)

- Branch: `feature/recepia-landing-premium-v1`. A alteração em `main.py` adicionou somente o mount `/assets`, limitado a `landing/assets`.
- 51 testes locais passaram: `test_landing.py`, `test_presentation.py`, `test_signup_api.py`, `test_segment_ui.py`, `test_auth_api.py`, `test_conversas_agent.py` e `test_openrouter.py`.
- O smoke `tests/segment_ui_smoke.cjs` e a verificação sintática de `landing.js` com `node --check` também passaram.
- FastAPI/Uvicorn local respondeu HTTP 200 em `/`, `/cadastro`, `/dashboard/`, `/dashboard/saas.html`, `/dashboard/admin.html`, `/health`, CSS, JavaScript, MP4, `robots.txt` e `sitemap.xml`.
- Chromium headless local: larguras de 320, 375, 390, 768, 1024, 1440 e 1920 px sem rolagem horizontal. Imagem hero carregou em todos os tamanhos.
- Desktop: vídeo WebM carregou e reproduziu; o botão de efeitos pausou o vídeo. Demonstração de agendamento concluiu seis mensagens e atualizou o painel. Cenário de preço, pausa, retomada, replay e alternância humano/IA funcionaram.
- Mobile: menu abriu e fechou; o vídeo não foi solicitado. Com movimento reduzido, o vídeo não foi solicitado e a demonstração foi exibida por completo.
- Nenhuma exceção JavaScript, erro de console ou falha de rede foi observada nessa sessão local. CTAs foram conferidos pelo destino no DOM; o domínio externo não foi acessado.
- Capturas desta integração: `preview-local-desktop.png` e `preview-local-mobile.png`. O teste usou viewports simulados, sem Safari ou aparelho físico.

## Interface

- Viewports 1920, 1366, 1024, 768, 390, 375 e 320 px sem rolagem horizontal.
- Desktop 1920×1080, notebook 1366×768 e mobile 390×844 capturados e revisados visualmente.
- Imagens carregadas; vídeo reproduziu no desktop e pausou com o controle.
- Todas as chamadas comerciais levam ao cadastro solicitado.
- Agendamento: seis mensagens e novo agendamento ilustrativo no painel.
- Preço, atendimento humano e informações: cenários concluídos.
- Pausa, retomada e replay da demonstração verificados.
- Alternância humano/IA nos dois sentidos e FAQ funcionando.
- Menu mobile abre, navega e fecha.
- Mobile e prefers-reduced-motion não solicitam MP4/WebM.
- Preferência de movimento reduzido exibe a conversa completa sem animação progressiva.
- Nenhum erro de console ou exceção de JavaScript na revisão final.
- Cadastro, dashboards SaaS/admin e CSS compartilhados idênticos aos arquivos do commit base, comparados por SHA-256.

## Performance

As medições abaixo são locais, em rede de loopback, sem simulação de CPU/rede móvel. Não são um relatório Lighthouse, resultados de produção ou garantia de Core Web Vitals.

- LCP local observado: 192 ms.
- CLS local observado: 0.0042.
- CSS aproximadamente 37 KB; JavaScript aproximadamente 15 KB, sem bibliotecas de animação.
- Fonte variável local WOFF2 aproximadamente 60 KB.
- Imagem desktop aproximadamente 115 KB; mobile aproximadamente 51 KB.
- Loop MP4 aproximadamente 175 KB; WebM aproximadamente 312 KB.
- Sem imagens de seção adicionais, CDN ou chamadas de IA na landing.
- Vídeo carregado após a imagem; a imagem do hero é priorizada, conteúdo abaixo da dobra não exige mídias adicionais.
- Animações CSS pausam fora da viewport. O vídeo e a demonstração pausam em aba oculta.

## Limites e próximos ajustes

Faltam testes em Safari/iPhone físico e medição no servidor público com rede móvel real. O loop existente é cinematográfico; um vídeo com gestos naturais é a principal melhoria visual futura. A integração real WhatsApp/IA depende do servidor e de sua configuração e foi preservada. Depoimentos reais e imagem de compartilhamento dedicada podem ser adicionados posteriormente.

## Capturas

- `desktop-1920x1080.png`
- `notebook-1366x768.png`
- `iphone-390x844.png`
- `desktop-demonstracao.png`
- `desktop-pagina-completa.png`
- `iphone-pagina-completa.png`

Dados de execução: `qa-results.json`.
