"""Detecção de plataforma e estratégias de download."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    THREADS = "threads"


@dataclass(frozen=True)
class DownloadStrategy:
    primary: str
    fallbacks: tuple[str, ...] = ()


_PLATFORM_PATTERNS: list[tuple[Platform, re.Pattern[str]]] = [
    (Platform.YOUTUBE, re.compile(r"(youtube\.com|youtu\.be)", re.I)),
    (Platform.INSTAGRAM, re.compile(r"instagram\.com", re.I)),
    (Platform.TIKTOK, re.compile(r"(tiktok\.com|vm\.tiktok\.com)", re.I)),
    (Platform.X, re.compile(r"(x\.com|twitter\.com)", re.I)),
    (Platform.THREADS, re.compile(r"threads\.net", re.I)),
]

_STRATEGIES: dict[Platform, DownloadStrategy] = {
    Platform.YOUTUBE: DownloadStrategy(primary="yt-dlp"),
    Platform.INSTAGRAM: DownloadStrategy(primary="instagrapi", fallbacks=("gallery-dl",)),
    Platform.TIKTOK: DownloadStrategy(primary="gallery-dl", fallbacks=("yt-dlp",)),
    Platform.X: DownloadStrategy(primary="yt-dlp"),
    Platform.THREADS: DownloadStrategy(primary="gallery-dl"),
}


def detect_platform(url: str) -> Optional[Platform]:
    for platform, pattern in _PLATFORM_PATTERNS:
        if pattern.search(url):
            return platform
    return None


def get_download_strategy(platform: Platform) -> DownloadStrategy:
    return _STRATEGIES[platform]
