# Landing institucional Recepia

A página está em `landing/index.html`, servida pela API em `/`. Assets exclusivos em `landing/assets/`, disponíveis em `/assets/`. Não depende de React, npm, CDN ou analytics. A fonte Plus Jakarta Sans é servida localmente em WOFF2, com licença OFL incluída. Cadastro e painéis não foram modificados.

## Visualizar localmente

Na pasta `recepia/` que contém `main.py`:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Configure as variáveis necessárias conforme `.env.example`, com valores próprios de desenvolvimento. A página fica em `http://localhost:8000/`. Não use credenciais reais apenas para revisar a landing.

Para visualizar só a landing, sem banco ou backend:

```bash
python -m http.server 8080 --directory landing
```

Abra `http://localhost:8080/`. Nesse modo, `/assets` funciona, mas login/documentos legais e cadastro locais dependem da API; os CTAs comerciais continuam apontando para o cadastro real.

## Vídeo da secretária

Substitua `landing/assets/recepia-secretaria-loop.mp4`. O site verifica sua existência automaticamente no desktop após carregar a imagem. Se fornecer um WebM, use `landing/assets/recepia-secretaria-loop.webm`. O arquivo mais recentemente modificado tem prioridade; WebM é preferido quando os dois têm a mesma data. Remova o WebM antigo ao substituir apenas o MP4 para evitar datas preservadas pelo processo de publicação.

Recomendação: 6–12 segundos, loop suave, sem áudio, H.264, 1280×720 ou 1920×1080, `faststart`, tamanho ideal abaixo de 2 MB. Para converter:

```bash
ffmpeg -i video-original.mp4 -an -vf scale=1280:-2 -c:v libx264 -crf 25 -preset slow -movflags +faststart landing/assets/recepia-secretaria-loop.mp4
ffmpeg -i video-original.mp4 -an -vf scale=1280:-2 -c:v libvpx-vp9 -crf 36 -b:v 0 landing/assets/recepia-secretaria-loop.webm
```

A imagem permanece quando o vídeo falta ou o autoplay é bloqueado. Em mobile, movimento reduzido, economia de dados e conexões 2G/3G, o vídeo não é solicitado. O hero usa o fallback responsivo com efeitos mais leves. Troque também `secretaria-fallback.webp` e `secretaria-mobile.webp` se o novo vídeo tiver composição diferente.

## Domínio e conversão

O endereço real solicitado está em:

- `landing/assets/landing.js`: `SIGNUP_URL`.
- `landing/index.html`: href de cada CTA, canonical, `og:url` e URL do JSON-LD.
- `landing/robots.txt`: URL do sitemap.
- `landing/sitemap.xml`: URLs indexáveis.

Faça uma substituição desses endereços em conjunto ao migrar. Confirme também canonical/analytics de `cadastro.html`, `entrar.html`, `termos.html` e `privacidade.html`, que foram preservados neste trabalho. O endereço técnico não aparece no texto visual da landing.

## Conteúdo e melhorias

Edite textos em `index.html`, paleta/ritmo em `assets/landing.css` e cenários ilustrativos em `assets/landing.js`. Os exemplos não criam dados nem conversas reais. O template `testimonial-template` e o contêiner `real-testimonials` estão ocultos, prontos para depoimentos autorizados reais; não publique avaliações inventadas.

Melhorias futuras: filmagem/vídeo com gestos naturais, depoimentos verificados, imagem social dedicada, medição de conversão com consentimento/política adequada e teste de desempenho no domínio definitivo com rede móvel real. Os metadados sociais atuais não apontam para uma imagem inexistente.
