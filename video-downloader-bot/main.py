"""Entry point — polling ou webhook FastAPI."""

from __future__ import annotations

import asyncio
import atexit

from fastapi import FastAPI, Request, Response
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from src.core.downloader import VideoDownloader
from src.handlers.message_processor import MessageProcessor
from src.handlers.telegram_handler import create_router, run_polling
from src.utils.config import get_settings
from src.utils.instance_lock import InstanceAlreadyRunningError, acquire_instance_lock, release_instance_lock
from src.utils.logging import setup_logging

logger = setup_logging()

app = FastAPI(title="Video Download Agent", version="1.0.0")
_bot: Bot | None = None
_dp: Dispatcher | None = None


def _get_bot_deps() -> tuple[Bot, Dispatcher, MessageProcessor, VideoDownloader, Settings]:
    global _bot, _dp
    settings = get_settings()
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
        _dp = Dispatcher()
        processor = MessageProcessor(settings)
        downloader = VideoDownloader(settings)
        _dp.include_router(create_router(settings, processor, downloader))
        return _bot, _dp, processor, downloader, settings
    processor = MessageProcessor(settings)
    downloader = VideoDownloader(settings)
    return _bot, _dp, processor, downloader, settings


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    settings = get_settings()
    if settings.webhook_secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != settings.webhook_secret:
            return Response(status_code=403)

    bot, dp, _, _, _ = _get_bot_deps()
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return Response(status_code=200)


async def setup_webhook(settings: Settings) -> None:
    if not settings.webhook_url:
        raise ValueError("WEBHOOK_URL é obrigatório para BOT_MODE=webhook")
    bot, _, _, _, _ = _get_bot_deps()
    await bot.set_webhook(
        url=f"{settings.webhook_url.rstrip('/')}/webhook",
        secret_token=settings.webhook_secret or None,
        drop_pending_updates=True,
    )
    me = await bot.get_me()
    logger.info("Webhook configurado para @%s", me.username)


def main() -> None:
    settings = get_settings()
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    setup_logging(settings.log_level, settings.local_storage_path / "logs")

    if settings.bot_mode == "polling":
        lock_path = settings.local_storage_path / "bot.lock"
        try:
            acquire_instance_lock(lock_path)
            atexit.register(release_instance_lock, lock_path)
        except InstanceAlreadyRunningError as exc:
            logger.error("%s", exc)
            raise SystemExit(1) from exc

    if settings.bot_mode == "webhook":
        import uvicorn

        asyncio.run(setup_webhook(settings))
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    else:
        asyncio.run(run_polling(settings))


if __name__ == "__main__":
    main()
