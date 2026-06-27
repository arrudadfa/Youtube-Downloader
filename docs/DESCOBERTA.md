# DESCOBERTA — Video Download Agent

**Status:** Aprovada (spec fornecida pelo usuário em 2026-06-27)

## Objetivo

Bot Telegram pessoal que baixa vídeos de YouTube, Instagram, TikTok, Threads e X, comprime se necessário e envia ao usuário.

## Contexto Telegram

- Bot: **Video Download Agent** (@ytig_dlp_bot)
- Modo: DM (mensagens privadas)
- Owner gratuito: user id `163177765` (@arrudadfa)
- Demais usuários: 1 Telegram Star por download

## Plataformas e estratégias

| Plataforma | Principal | Fallback |
|------------|-----------|----------|
| YouTube | yt-dlp | — |
| Instagram | instagrapi | gallery-dl |
| TikTok | gallery-dl | yt-dlp |
| X (Twitter) | yt-dlp | — |
| Threads | gallery-dl | — |

## Constraints

- Timeout: 120s por download
- Limite Telegram: 50MB (compressão FFmpeg)
- Max downloads concorrentes: 3
- Storage: local ou S3

## Decisões de arquitetura

- Polling como modo padrão; FastAPI webhook opcional via `BOT_MODE`
- aiogram 3.x para integração Telegram
- Lógica de download isolada em `src/core/`
- TDD com pytest

## Fora de escopo v1

- Grupos/canais
- Painel admin web
- Histórico persistente de downloads
