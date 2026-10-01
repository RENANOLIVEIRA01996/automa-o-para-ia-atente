# Tour de apresentação do Recepia

O vídeo é um tour de 111 segundos pelo **aplicativo real**, em português do Brasil, 16:9 e 1920×1080. As capturas foram feitas em uma instância local isolada com dados identificados como demonstração. Elas mostram WhatsApp, conversas, clientes, serviços, profissionais, agenda, painel, configurações da IA e dados da empresa. Os módulos de pets, veículos e hotel aparecem como possibilidade condicionada ao segmento, sem simular telas inexistentes.

Arquivos de produção:

- `scenes.json`: ordem, duração, títulos e texto de cada cena;
- `storyboard.md`: sequência com tempo de entrada e saída;
- `narration.md`: texto completo para gravar locução brasileira;
- `subtitles.srt`: legendas de todas as cenas;
- `assets/screenshots/`: capturas reais da instância local;
- `../../scripts/render_presentation.py`: gera o MP4 horizontal;
- `../../public/media/recepia-apresentacao.mp4`: arquivo servido pela API.

O MP4 gerado aqui tem **faixa de áudio silenciosa** porque este ambiente não oferece voz brasileira. As frases do tour aparecem na tela, e o roteiro e o SRT estão prontos para gravar uma locução e substituir o áudio. Para trocar a faixa de áudio sem recodificar o vídeo:

```bash
ffmpeg -i public/media/recepia-apresentacao.mp4 -i locucao-ptbr.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 128k -shortest \
  public/media/recepia-apresentacao-com-voz.mp4
```

Depois, substitua `recepia-apresentacao.mp4` pelo resultado e valide com `ffprobe`.

## Renderizar de novo

Na pasta `recepia`, com FFmpeg no PATH e Pillow instalado:

```bash
python scripts/render_presentation.py
```

Para alterar o conteúdo, edite `docs/presentation/scenes.json`. Se a interface mudar, capture novamente as telas do próprio aplicativo em uma instância de demonstração e substitua apenas os PNGs correspondentes em `assets/screenshots/`. O script falha se uma captura esperada estiver ausente; ele nunca cria uma tela falsa. O vídeo final deve manter o nome `public/media/recepia-apresentacao.mp4`.

## Publicação e teste do WhatsApp

1. Configure `PUBLIC_BASE_URL=https://SEU-DOMINIO` no ambiente da API ou use `DOMAIN`/`APP_URL` HTTPS já configurados. `PUBLIC_WEBHOOK_URL` pode ser interno e não é usado para mídia.
2. Prepare a migração aditiva do banco antes de iniciar a versão nova: `python scripts/prepare_database.py --apply`. Na Oracle, siga o procedimento de banco da documentação de deploy antes de recriar a imagem da API.
3. Recrie a imagem da API para incluir o novo MP4, ou monte um volume no mesmo caminho. A URL pública esperada é `https://SEU-DOMINIO/media/recepia-apresentacao.mp4`.
4. Confirme que a URL responde `200`, com `Content-Type: video/mp4`, e que o vídeo abre fora de uma sessão autenticada. A Evolution precisa conseguir baixá-lo.
5. No WhatsApp conectado ao tenant comercial `RECEPIA`, envie exatamente: **Tem vídeo de apresentação?**. Em outra conversa, teste **Como funciona o Recepia?**. Para reenvio, use **Me manda o vídeo de novo**.
6. Confira logs da API por `Vídeo de apresentação enviado`, `Vídeo de apresentação indisponível` ou `Envio do vídeo falhou`; observe os logs da Evolution se o `sendMedia` retornar erro HTTP. O cliente recebe texto explicativo sem detalhes técnicos quando a mídia falha.

A configuração no painel do tenant comercial permite desligar o envio automático e ajustar a legenda. Outros tenants não recebem a tool do vídeo oficial.
