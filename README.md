# Video Download Agent

Bot Telegram (@ytig_dlp_bot) que baixa vídeos de **YouTube**, **Instagram**, **TikTok**, **X** e **Threads**, comprime se necessário (limite 50MB) e envia ao usuário.

## Arquitetura

```
video-downloader-bot/
├── src/
│   ├── core/           # downloader, platforms, validators
│   ├── handlers/       # telegram + message_processor
│   ├── storage/        # local / S3
│   └── utils/          # config, logging
├── tests/              # pytest (TDD)
├── scripts/            # testes isolados por downloader
├── main.py             # polling ou webhook FastAPI
└── docs/               # DESCOBERTA.md + SPEC.md
```

## Pré-requisitos

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) no PATH
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) e [gallery-dl](https://github.com/mikf/gallery-dl) instalados

```bash
pip install -r requirements.txt
pip install yt-dlp gallery-dl
```

## Configuração

```bash
cp .env.example .env
# Edite TELEGRAM_BOT_TOKEN com o token do @BotFather
```

| Variável | Descrição |
|----------|-----------|
| `TELEGRAM_BOT_TOKEN` | Token do bot |
| `OWNER_USER_ID` | ID gratuito (padrão: 163177765) |
| `STAR_PRICE` | Estrelas cobradas por download (padrão: 1) |
| `BOT_MODE` | `polling` ou `webhook` |
| `MAX_VIDEO_SIZE_MB` | Limite Telegram (50) |
| `INSTAGRAM_USERNAME/PASSWORD` | Para instagrapi |
| `INSTAGRAM_VERIFICATION_CODE` | Código TOTP (opcional; prefira `/ig2fa`) |
| `INSTAGRAM_SESSION_PATH` | Sessão salva após login (padrão: `./data/instagram_session.json`) |
| `INSTAGRAM_COOKIES_PATH` | Arquivo `cookies.txt` (Netscape) para gallery-dl — opcional |
| `INSTAGRAM_COOKIES_BROWSER` | Cookies do navegador para gallery-dl (`chrome`, `firefox`, `edge`) |

## Instagram com 2FA

1. Preencha `INSTAGRAM_USERNAME` e `INSTAGRAM_PASSWORD` no `.env`
2. Inicie o bot e envie **`/ig2fa 123456`** (código do autenticador, válido ~30s)
3. A sessão é salva em `data/instagram_session.json` — não precisa repetir a cada download
4. Alternativa: `INSTAGRAM_VERIFICATION_CODE` no `.env` só na primeira autenticação

### Cookies para gallery-dl

O `gallery-dl` precisa de cookies de login no Instagram. Há **3 formas** (em ordem de prioridade):

1. **Automático (recomendado)** — após `/ig2fa`, o bot exporta cookies de `data/instagram_session.json` para `data/instagram_gallery_cookies.txt` e passa `-C` ao gallery-dl no fallback.

2. **Arquivo manual** — exporte cookies do navegador (extensão *Get cookies.txt LOCALLY* ou similar) e configure:
   ```env
   INSTAGRAM_COOKIES_PATH=./data/instagram_cookies.txt
   ```

3. **Direto do navegador** — o gallery-dl lê cookies do Chrome/Firefox/Edge:
   ```env
   INSTAGRAM_COOKIES_BROWSER=chrome
   ```
   O navegador precisa estar logado no Instagram na mesma máquina do bot.

## Deploy na VPS (Easypanel / Hostinger)

Na VPS **não use** `INSTAGRAM_COOKIES_BROWSER` — não há Chrome/Firefox logado no servidor.

### Variáveis no Easypanel

| Variável | Valor |
|----------|--------|
| `INSTAGRAM_USERNAME` | seu usuário |
| `INSTAGRAM_PASSWORD` | sua senha |
| `INSTAGRAM_SESSION_PATH` | `./data/instagram_session.json` |
| `BOT_MODE` | `polling` (mais simples; webhook exige domínio) |

Deixe `INSTAGRAM_COOKIES_BROWSER` **vazio**.

### Volume persistente (importante)

Monte um volume em **`/app/data`** no Easypanel. Sem isso, a sessão Instagram se perde a cada redeploy e você precisa refazer o `/ig2fa`.

Após o primeiro login, o bot salva:

- `data/instagram_session.json` — sessão instagrapi
- `data/instagram_gallery_cookies.txt` — cookies para gallery-dl (exportados automaticamente)

### Autenticar na VPS

1. Faça deploy com usuário/senha Instagram nas env vars
2. Abra o bot no Telegram e envie **`/ig2fa 123456`** (código do autenticador, ~30s)
3. Aguarde `✅ Instagram autenticado!`
4. Teste com um link do Instagram

### Alternativa: cookies do PC

Se preferir não usar `/ig2fa` na VPS:

1. No seu PC, exporte cookies do Instagram (extensão *Get cookies.txt LOCALLY*)
2. Envie o arquivo para a VPS (SFTP ou file manager do Easypanel)
3. Coloque em `/app/data/instagram_cookies.txt`
4. Configure `INSTAGRAM_COOKIES_PATH=./data/instagram_cookies.txt`

Cookies do navegador expiram mais rápido que a sessão instagrapi — o `/ig2fa` costuma ser mais estável.

## Executar

```bash
# Polling (recomendado para dev)
python main.py

# Webhook
BOT_MODE=webhook WEBHOOK_URL=https://seu-dominio.com python main.py
```

## Acesso

- **Owner** (`163177765` / [@arrudadfa](https://t.me/arrudadfa)): downloads gratuitos
- **Outros usuários**: 1 Telegram Star por vídeo

## Testes

```bash
pytest tests/ -v
```

## Teste manual por downloader

```bash
python scripts/test_downloaders.py auto "https://youtube.com/watch?v=..."
python scripts/test_downloaders.py ytdlp "https://x.com/user/status/..."
python scripts/test_downloaders.py gallery-dl "https://www.tiktok.com/@user/video/..."
```

## Estratégias por plataforma

| Plataforma | Principal | Fallback |
|------------|-----------|----------|
| YouTube | yt-dlp | — |
| Instagram | instagrapi | gallery-dl |
| TikTok | gallery-dl | yt-dlp |
| X | yt-dlp | — |
| Threads | gallery-dl | — |

## BotFather

- **Name**: Video Download Agent
- **Username**: @ytig_dlp_bot

Para cobrar Stars, habilite pagamentos no [@BotFather](https://t.me/BotFather) → Bot Settings → Payments.
