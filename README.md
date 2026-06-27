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

## Instagram com 2FA

1. Preencha `INSTAGRAM_USERNAME` e `INSTAGRAM_PASSWORD` no `.env`
2. Inicie o bot e envie **`/ig2fa 123456`** (código do autenticador, válido ~30s)
3. A sessão é salva em `data/instagram_session.json` — não precisa repetir a cada download
4. Alternativa: `INSTAGRAM_VERIFICATION_CODE` no `.env` só na primeira autenticação

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
