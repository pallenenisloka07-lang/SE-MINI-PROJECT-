
import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "documents.db"


class DocumentManager:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or os.getenv("DOCUMENTS_DB_PATH", DEFAULT_DB_PATH))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """)
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(documents)")
            }
            if "owner_id" not in columns:
                # Preserve any pre-existing documents but keep them private
                # until they are explicitly assigned to a user.
                db.execute(
                    "ALTER TABLE documents ADD COLUMN owner_id INTEGER"
                )

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _document(row):
        return {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
        }

    @staticmethod
    def _validate(title, content):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Title is required")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Content is required")

    def add(self, owner_id, title, content):
        self._validate(title, content)
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO documents (owner_id, title, content)
                   VALUES (?, ?, ?)""",
                (owner_id, title.strip(), content.strip()),
            )
            return cursor.lastrowid

    def view_all(self, owner_id):
        with self._connect() as db:
            rows = db.execute(
                """SELECT id, title, content FROM documents
                   WHERE owner_id = ? ORDER BY id DESC""",
                (owner_id,),
            ).fetchall()
            return [self._document(row) for row in rows]

    def get(self, owner_id, doc_id):
        with self._connect() as db:
            row = db.execute(
                """SELECT id, title, content FROM documents
                   WHERE owner_id = ? AND id = ?""",
                (owner_id, doc_id),
            ).fetchone()
            return self._document(row) if row else None

    def search(self, owner_id, keyword):
        with self._connect() as db:
            rows = db.execute(
                """SELECT id, title, content FROM documents
                   WHERE owner_id = ? AND title LIKE ?
                   ORDER BY id DESC""",
                (owner_id, f"%{keyword}%"),
            ).fetchall()
            return [self._document(row) for row in rows]

    def edit(self, owner_id, doc_id, title, content):
        self._validate(title, content)
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE documents SET title = ?, content = ?
                   WHERE owner_id = ? AND id = ?""",
                (title.strip(), content.strip(), owner_id, doc_id),
            )
            return cursor.rowcount > 0

    def delete(self, owner_id, doc_id):
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM documents WHERE owner_id = ? AND id = ?",
                (owner_id, doc_id),
            )
            return cursor.rowcount > 0
