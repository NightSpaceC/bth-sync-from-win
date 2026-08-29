import os
import tempfile
from pathlib import Path

from .errors import FileSystemError


def ensure_directory(path: Path, mode: int = 0o700) -> bool:
    try:
        if path.is_symlink():
            raise FileSystemError(f"{path} is a symlink; refusing to manage it")

        if path.exists():
            if not path.is_dir():
                raise FileSystemError(f"{path} exists and is not a directory")
            os.chmod(path, mode)
            return False

        path.mkdir(mode=mode)
        os.chmod(path, mode)
        return True
    except FileSystemError:
        raise
    except OSError as exc:
        raise FileSystemError(f"Cannot ensure directory {path}: {exc}") from exc


def ensure_empty_file(path: Path, mode: int = 0o600) -> bool:
    try:
        if path.is_symlink():
            raise FileSystemError(f"{path} is a symlink; refusing to manage it")

        if path.exists():
            if not path.is_file():
                raise FileSystemError(f"{path} exists and is not a regular file")
            os.chmod(path, mode)
            return False

        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
        os.close(fd)
        os.chmod(path, mode)
        return True
    except FileSystemError:
        raise
    except OSError as exc:
        raise FileSystemError(f"Cannot ensure file {path}: {exc}") from exc


def write_text_atomic(path: Path, text: str, mode: int = 0o600) -> None:
    try:
        if path.is_symlink():
            raise FileSystemError(f"{path} is a symlink; refusing to write it")

        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as tmp_file:
                tmp_file.write(text)

            os.chmod(tmp_path, mode)
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except FileSystemError:
        raise
    except OSError as exc:
        raise FileSystemError(f"Cannot write {path}: {exc}") from exc
