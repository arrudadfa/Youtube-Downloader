"""Handlers Telegram (polling e webhook)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from src.core.downloader import DownloadError, VideoDownloader
from src.core.instagram_auth import InstagramAuthError, InstagramSessionManager
from src.handlers.message_processor import MessageProcessor, ProcessResult, is_owner
from src.utils.config import Settings
from src.utils.logging import setup_logging

if TYPE_CHECKING:
    pass

logger = setup_logging()


def create_router(settings: Settings, processor: MessageProcessor, downloader: VideoDownloader) -> Router:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "🎬 *Video Download Agent*\n\n"
            "Envie a URL de um vídeo para baixar.\n"
            "Plataformas: YouTube, Instagram, TikTok, X, Threads.\n\n"
            "Use /help para mais detalhes.",
            parse_mode="Markdown",
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(processor.SUPPORTED_MSG)

    @router.message(Command("ig2fa"))
    async def cmd_ig2fa(message: Message) -> None:
        if not message.from_user or not is_owner(message.from_user.id, settings):
            await message.answer("Comando restrito ao owner.")
            return
        if not message.text:
            return
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            await message.answer(
                "Uso: /ig2fa <código de 6 dígitos>\n"
                "Pegue o código no app autenticador do Instagram (válido ~30s)."
            )
            return

        code = parts[1].strip()
        ig = InstagramSessionManager.for_settings(settings)
        ig.set_verification_code(code)

        try:
            await asyncio.to_thread(ig.get_client)
            await message.answer("✅ Instagram autenticado! Sessão salva. Pode enviar URLs do Instagram.")
        except InstagramAuthError as exc:
            await message.answer(f"❌ Falha no 2FA: {exc}")
        except Exception as exc:
            logger.exception("Erro no login Instagram 2FA")
            await message.answer(f"❌ Erro no login: {exc}")

    @router.message(F.text)
    async def handle_text(message: Message, bot: Bot) -> None:
        if not message.from_user or not message.text:
            return

        user_id = message.from_user.id
        result = processor.process_text(message.text, user_id)

        if result.action == "ignore":
            return
        if result.action == "error":
            await message.answer(result.message or "Erro.")
            return
        if result.action == "invoice":
            await _send_star_invoice(bot, message, result, settings)
            return
        if result.action == "download" and result.url:
            await _execute_download(message, bot, result.url, downloader)

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def successful_payment(message: Message, bot: Bot) -> None:
        if not message.successful_payment or not message.from_user:
            return
        payload = message.successful_payment.invoice_payload
        url = processor.pop_pending_url(payload)
        if not url:
            await message.answer("Pagamento recebido, mas a URL expirou. Envie o link novamente.")
            return
        await message.answer("✅ Pagamento confirmado! Iniciando download...")
        await _execute_download(message, bot, url, downloader)

    return router


async def _send_star_invoice(
    bot: Bot,
    message: Message,
    result: ProcessResult,
    settings: Settings,
) -> None:
    if not message.chat:
        return
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Download de vídeo",
        description=f"1 vídeo ({result.platform})",
        payload=result.payload or "",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Download", amount=settings.star_price)],
    )


async def _execute_download(
    message: Message,
    bot: Bot,
    url: str,
    downloader: VideoDownloader,
) -> None:
    status_msg = await message.answer("⏳ Validando URL...")
    download_result = None

    async def update_progress(text: str) -> None:
        try:
            await status_msg.edit_text(f"⏳ {text}")
        except Exception:
            pass

    async def on_progress(text: str) -> None:
        await update_progress(text)

    try:
        download_result = await downloader.download(url, progress_callback=on_progress)
        await update_progress("Enviando vídeo...")
        video = FSInputFile(download_result.file_path)
        await message.answer_video(
            video,
            caption=f"✅ {download_result.title}\n📦 {download_result.size_bytes // 1024 // 1024} MB",
        )
        await status_msg.delete()
    except DownloadError as exc:
        logger.error("DownloadError para %s: %s", url, exc)
        await status_msg.edit_text(f"❌ {exc}")
    except asyncio.TimeoutError:
        logger.error("Timeout para %s", url)
        await status_msg.edit_text("❌ Timeout: o download excedeu o tempo limite.")
    except Exception as exc:
        logger.exception("Erro inesperado para %s", url)
        await status_msg.edit_text(f"❌ Erro inesperado: {exc}")
    finally:
        if download_result is not None:
            downloader.cleanup(download_result.file_path)


async def run_polling(settings: Settings) -> None:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    processor = MessageProcessor(settings)
    downloader = VideoDownloader(settings)
    router = create_router(settings, processor, downloader)
    dp.include_router(router)

    me = await bot.get_me()
    logger.info("Bot iniciado: @%s (polling)", me.username)
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()
