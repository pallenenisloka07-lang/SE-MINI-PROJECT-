
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STORAGE_DIR = PROJECT_ROOT / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def save_file(file_bytes: bytes, original_filename: str) -> str:
    """Save validated-size file bytes under a generated filename."""
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 10 MB upload limit.")

    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, DOCX, and TXT files are supported.")

    generated_name = f"{uuid4()}{extension}"
    destination = STORAGE_DIR / generated_name

    with destination.open("xb") as file:
        file.write(file_bytes)

    return str(destination.relative_to(PROJECT_ROOT))


def get_file(storage_path: str) -> Path:
    """Resolve a stored path while preventing path traversal."""
    relative_path = Path(storage_path)

    if relative_path.is_absolute():
        raise ValueError("Invalid storage path.")

    destination = (PROJECT_ROOT / relative_path).resolve()
    allowed_root = STORAGE_DIR.resolve()

    if not destination.is_relative_to(allowed_root):
        raise ValueError("Invalid storage path.")

    if not destination.is_file():
        raise FileNotFoundError("Stored file not found.")

    return destination


def delete_file(storage_path: str) -> bool:
    """Delete a stored file if it exists."""
    try:
        get_file(storage_path).unlink()
        return True
    except FileNotFoundError:
        return False

