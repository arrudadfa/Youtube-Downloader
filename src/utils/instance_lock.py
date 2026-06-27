"""Garante que apenas uma instância do bot rode por vez (polling)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_lock_handle: object | None = None


class InstanceAlreadyRunningError(RuntimeError):
    pass


def acquire_instance_lock(lock_path: Path) -> None:
    global _lock_handle
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = open(lock_path, "a+", encoding="utf-8")
    try:
        if sys.platform == "win32":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        lock_file.close()
        raise InstanceAlreadyRunningError(
            "Outra instância do bot já está rodando. "
            "Encerre o processo anterior antes de iniciar outra."
        ) from exc

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    _lock_handle = lock_file


def release_instance_lock(lock_path: Path, expected_pid: int | None = None) -> None:
    global _lock_handle
    if _lock_handle is None:
        return
    try:
        if sys.platform == "win32":
            import msvcrt

            _lock_handle.seek(0)
            msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_UN)
        _lock_handle.close()
    except OSError:
        pass
    finally:
        _lock_handle = None
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
