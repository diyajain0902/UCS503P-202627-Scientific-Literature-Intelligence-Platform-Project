from pathlib import Path

import pytest

from app.ingestion.storage import FileStore

SHA = "0123456789abcdef" * 4


def test_save_read_delete_roundtrip(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    key = store.save(SHA, b"%PDF-data")
    assert key == f"{SHA}.pdf"
    assert store.read(key) == b"%PDF-data"
    assert store.save(SHA, b"%PDF-data") == key  # idempotent
    store.delete(key)
    assert not store.exists(key)
    store.delete(key)  # deleting twice is harmless


@pytest.mark.parametrize(
    "key", ["../secret.pdf", "..\\secret.pdf", "/etc/passwd", f"{SHA}.exe", "A" * 64 + ".pdf", ""]
)
def test_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(ValueError):
        store.read(key)


def test_no_temp_files_left_behind(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    store.save(SHA, b"%PDF-data")
    assert [p.name for p in tmp_path.iterdir()] == [f"{SHA}.pdf"]
