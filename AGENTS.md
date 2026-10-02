# Recepia — instruções para Codex e outros agentes

## Landing institucional atual

A versão escolhida pelo usuário é **Recepia Landing Premium v1**, criada em 01/10/2026. Use esta versão ao trabalhar no site institucional. Não volte às versões antigas `recepia-preview`, `recepia-super-site`, `recepia-site-profissional` ou `recepia-site-cinematografico` sem uma nova instrução do usuário.

- Página principal: `recepia/landing/index.html`, servida em `/`.
- CSS e JavaScript próprios: `recepia/landing/assets/landing.css` e `landing.js`.
- Vídeo: `recepia/landing/assets/recepia-secretaria-loop.mp4`, com WebM opcional.
- Fallbacks WebP e fonte local: `recepia/landing/assets/`.
- Instruções para execução, vídeo e domínio: `recepia/landing/README.md`.
- Auditoria: `recepia/docs/landing/AUDITORIA.md`.
- Validação e screenshots: `recepia/docs/landing/VALIDACAO.md`.
- Testes da landing: `recepia/tests/test_landing.py`.
- Páginas comerciais e preparação para busca: `recepia/docs/SEO_ORACLE.md`.

A stack é FastAPI/Python com frontend estático HTML/CSS/JavaScript. Não migre para React/Next.js apenas para rodar esta landing. `main.py` precisa manter o mount de `/assets` limitado a `landing/assets`.

## Executar localmente

Entre na pasta `recepia/` que contém `main.py`, configure variáveis de desenvolvimento conforme `.env.example`, instale `requirements.txt` e execute:

```bash
uvicorn main:app --reload --port 8000
```

Abra `http://localhost:8000/`.

Para uma prévia apenas visual sem backend:

```bash
python -m http.server 8080 --directory recepia/landing
```

Execute esse segundo comando na raiz do repositório e abra `http://localhost:8080/`. Login e documentos legais locais dependem da API; os CTAs comerciais levam ao cadastro real.

## Preservar o sistema existente

Mantenha `/cadastro`, `/dashboard`, `/dashboard/saas.html`, `/dashboard/admin.html`, autenticação, APIs e estilos compartilhados. A demonstração da landing é fictícia e não deve criar agendamentos ou mensagens reais.

Os CTAs de cadastro usam `/cadastro` na mesma origem; o domínio canônico e os links externos da IA vêm de `PUBLIC_SITE_URL`. Consulte o README antes de trocar domínio. Não exponha credenciais ou arquivos `.env` em assets, frontend ou logs. Não publique depoimentos ou números de clientes inventados.

Não faça deploy, commit ou push sem autorização do usuário. O pedido original autorizou desenvolvimento e validação local.

## Origem do pacote

Pacote de referência: `Recepia-Landing-Premium-v1.zip`, disponibilizado nesta conversa. Base do repositório: `2a66e38170250184bfa6c6611148bfad531f6755`, em `https://github.com/RENANOLIVEIRA01996/automa-o-para-ia-atente`.

Se o repositório tiver avançado desde essa base, compare as alterações antes de integrar o pacote. Em `main.py`, a mudança da landing é somente a definição de `LANDING_ASSETS_DIR` e o mount estático de `/assets`; preserve outras mudanças do backend.
