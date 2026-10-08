"""Content-addressed PDF storage. Keys are server-generated (``<sha256>.pdf``); user input never
forms a path.
"""

import os
import re
import tempfile
from pathlib import Path

_KEY_RE = re.compile(r"^[0-9a-f]{64}\.pdf$")


class FileStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY_RE.fullmatch(key):
            raise ValueError("invalid storage key")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("storage key escapes storage root")
        return path

    @staticmethod
    def key_for(sha256: str) -> str:
        return f"{sha256}.pdf"

    def save(self, sha256: str, data: bytes) -> str:
        key = self.key_for(sha256)
        path = self._path(key)
        if path.exists():
            return key
        fd, tmp_name = tempfile.mkstemp(dir=self._root, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
