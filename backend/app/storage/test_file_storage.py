
import pytest

from backend.app.storage import file_storage


@pytest.fixture
def temporary_storage(tmp_path, monkeypatch):
    """Use a temporary directory so tests do not affect real stored files."""
    monkeypatch.setattr(file_storage, "PROJECT_ROOT", tmp_path)

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    monkeypatch.setattr(file_storage, "STORAGE_DIR", storage_dir)

    return storage_dir


def test_save_and_get_file(temporary_storage):
    content = b"Test document content"

    storage_path = file_storage.save_file(content, "sample.txt")
    saved_path = file_storage.get_file(storage_path)

    assert saved_path.exists()
    assert saved_path.read_bytes() == content
    assert saved_path.parent == temporary_storage


def test_save_file_generates_unique_names(temporary_storage):
    first = file_storage.save_file(b"First", "sample.txt")
    second = file_storage.save_file(b"Second", "sample.txt")

    assert first != second


def test_save_file_rejects_empty_content(temporary_storage):
    with pytest.raises(ValueError, match="empty"):
        file_storage.save_file(b"", "sample.txt")


def test_save_file_rejects_files_over_10_mb(temporary_storage):
    oversized_content = b"x" * (file_storage.MAX_FILE_SIZE + 1)

    with pytest.raises(ValueError, match="10 MB"):
        file_storage.save_file(oversized_content, "sample.txt")


@pytest.mark.parametrize("filename", ["sample.exe", "sample.jpg", "sample"])
def test_save_file_rejects_unsupported_extensions(
    temporary_storage, filename
):
    with pytest.raises(ValueError, match="Only PDF, DOCX, and TXT"):
        file_storage.save_file(b"content", filename)


def test_delete_file(temporary_storage):
    storage_path = file_storage.save_file(b"Delete me", "sample.txt")

    assert file_storage.delete_file(storage_path) is True
    assert not (temporary_storage / storage_path.split("/", 1)[-1]).exists()


def test_delete_missing_file_returns_false(temporary_storage):
    assert file_storage.delete_file("storage/missing.txt") is False


def test_get_file_rejects_path_traversal(temporary_storage):
    with pytest.raises(ValueError, match="Invalid storage path"):
        file_storage.get_file("storage/../../outside.txt")


def test_get_file_rejects_absolute_paths(temporary_storage, tmp_path):
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("not allowed")

    with pytest.raises(ValueError, match="Invalid storage path"):
        file_storage.get_file(str(outside_file))

