
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

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

    # Normalize both Windows and POSIX separators before interpreting the name.
    safe_name = (original_filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, DOCX, and TXT files are supported.")

    # Reject obvious extension/content mismatches *before* touching storage.
    # Structural extraction failures are handled separately by the processor.
    if extension == ".pdf" and not file_bytes.startswith(b"%PDF-"):
        raise ValueError("The file content does not match PDF format.")
    if extension == ".docx":
        try:
            with ZipFile(BytesIO(file_bytes)) as archive:
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(
                    archive.namelist()
                ):
                    raise ValueError("The file content does not match DOCX format.")
        except (BadZipFile, OSError) as exc:
            raise ValueError("The file content does not match DOCX format.") from exc
    if extension == ".txt":
        if b"\x00" in file_bytes:
            raise ValueError("The TXT file contains binary data.")
        try:
            file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("The TXT file must use UTF-8 encoding.") from exc

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

