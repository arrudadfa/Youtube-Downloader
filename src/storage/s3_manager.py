"""Gerenciamento de storage local ou S3."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.utils.config import Settings
from src.utils.logging import setup_logging

logger = setup_logging()


class StorageManager:
    """Salva arquivos localmente ou envia para S3."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local_path = settings.local_storage_path
        self._local_path.mkdir(parents=True, exist_ok=True)

    def get_local_path(self, filename: str) -> Path:
        return self._local_path / filename

    async def store(self, file_path: Path) -> str:
        if self.settings.storage_type == "s3":
            return await self._upload_s3(file_path)
        return str(file_path.resolve())

    async def _upload_s3(self, file_path: Path) -> str:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 necessário para STORAGE_TYPE=s3") from exc

        s3 = boto3.client(
            "s3",
            region_name=self.settings.s3_region,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
        )
        key = file_path.name
        s3.upload_file(str(file_path), self.settings.s3_bucket, key)
        url = f"s3://{self.settings.s3_bucket}/{key}"
        logger.info("Upload S3 concluído: %s", url)
        return url

    def delete_local(self, file_path: Path) -> None:
        if file_path.exists():
            file_path.unlink()
