#!/usr/bin/env python3
"""Scripts de teste isolados por downloader.

Uso:
    python scripts/test_downloaders.py ytdlp <url>
    python scripts/test_downloaders.py gallery-dl <url>
    python scripts/test_downloaders.py instagrapi <url>
    python scripts/test_downloaders.py auto <url>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.core.downloader import DownloadError, VideoDownloader
from src.core.platforms import Platform, detect_platform, get_download_strategy
from src.utils.config import Settings


async def test_auto(url: str, settings: Settings) -> None:
    platform = detect_platform(url)
    if not platform:
        print("Plataforma não detectada.")
        sys.exit(1)
    strategy = get_download_strategy(platform)
    print(f"Plataforma: {platform.value}")
    print(f"Estratégia: {strategy.primary} -> {strategy.fallbacks}")
    downloader = VideoDownloader(settings)
    try:
        result = await downloader.download(url, progress_callback=lambda msg: print(f"  {msg}"))
        print(f"OK: {result.file_path} ({result.size_bytes} bytes)")
    except DownloadError as exc:
        print(f"ERRO: {exc}")
        sys.exit(1)


async def test_tool(tool: str, url: str, settings: Settings) -> None:
    downloader = VideoDownloader(settings)
    tool_map = {
        "ytdlp": downloader._download_ytdlp,
        "gallery-dl": downloader._download_gallery_dl,
        "instagrapi": downloader._download_instagrapi,
    }
    fn = tool_map.get(tool)
    if fn is None:
        print(f"Ferramenta desconhecida: {tool}")
        sys.exit(1)
    try:
        path = await fn(url)
        print(f"OK: {path} ({path.stat().st_size} bytes)")
    except Exception as exc:
        print(f"ERRO: {exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste isolado de downloaders")
    parser.add_argument("tool", choices=["ytdlp", "gallery-dl", "instagrapi", "auto"])
    parser.add_argument("url", help="URL do vídeo")
    args = parser.parse_args()

    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-for-scripts")
    settings = Settings()

    if args.tool == "auto":
        asyncio.run(test_auto(args.url, settings))
    else:
        asyncio.run(test_tool(args.tool, args.url, settings))


if __name__ == "__main__":
    main()
