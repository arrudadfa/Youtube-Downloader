# SPEC — Video Download Agent

**Versão:** v1.0 | **Status:** Aprovada

## User Stories

### US-01 — Owner baixa vídeo
**Given** user id `163177765`  
**When** envia URL suportada  
**Then** bot valida, baixa, comprime se >50MB, envia vídeo com feedback de progresso

### US-02 — Outro usuário paga com Star
**Given** user id ≠ owner  
**When** envia URL suportada  
**Then** bot envia invoice de 1 Star (XTR); após pagamento, executa download

### US-03 — URL inválida
**When** mensagem não contém URL suportada  
**Then** bot responde com plataformas aceitas

### US-04 — Erro de download
**When** download falha (429, privado, auth)  
**Then** bot informa erro amigável e registra log

## Comandos

| Entrada | Saída |
|---------|-------|
| /start | Boas-vindas + instruções |
| /help | Plataformas e limites |
| URL em texto | Fluxo de download (ou invoice) |

## Critérios de aceite

- [ ] Detecta YouTube, Instagram, TikTok, X, Threads
- [ ] Timeout 120s respeitado
- [ ] Compressão FFmpeg quando arquivo > MAX_VIDEO_SIZE_MB
- [ ] Owner id 163177765 sem cobrança
- [ ] Outros usuários: 1 Star antes do download
- [ ] Logs estruturados console + arquivo
- [ ] Scripts de teste isolados por downloader

## Variáveis de ambiente

Ver `.env.example`

## Changelog

| v1.0 | 2026-06-27 | Spec inicial |
