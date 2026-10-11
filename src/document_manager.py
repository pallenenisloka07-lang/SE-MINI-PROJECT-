
import sqlite3


class DocumentManager:
    def __init__(self, db_path="documents.db"):
        self.db_path = db_path

        # Create the documents table and close the connection.
        db = self._connect()
        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """)
            db.commit()
        finally:
            db.close()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _run(self, query, params=(), fetch=False):
        """Execute a query and always close the database connection."""
        db = self._connect()
        try:
            cursor = db.execute(query, params)

            if fetch:
                return cursor.fetchall()

            db.commit()
            return cursor.rowcount, cursor.lastrowid
        finally:
            db.close()

    def add(self, title, content):
        """Add a document and return its ID."""
        if not title.strip() or not content.strip():
            raise ValueError("Title and content are required")

        _, doc_id = self._run(
            "INSERT INTO documents (title, content) VALUES (?, ?)",
            (title.strip(), content.strip())
        )
        return doc_id

    def view_all(self):
        """Return all documents."""
        rows = self._run(
            "SELECT id, title, content FROM documents ORDER BY id",
            fetch=True
        )
        return [
            {"id": row[0], "title": row[1], "content": row[2]}
            for row in rows
        ]

    def search(self, keyword):
        """Search documents by title."""
        rows = self._run(
            """SELECT id, title, content
               FROM documents
               WHERE title LIKE ?
               ORDER BY id""",
            (f"%{keyword}%",),
            fetch=True
        )
        return [
            {"id": row[0], "title": row[1], "content": row[2]}
            for row in rows
        ]

    def edit(self, doc_id, title, content):
        """Update a document. Return True if it exists."""
        if not title.strip() or not content.strip():
            raise ValueError("Title and content are required")

        count, _ = self._run(
            """UPDATE documents
               SET title = ?, content = ?
               WHERE id = ?""",
            (title.strip(), content.strip(), doc_id)
        )
        return count > 0

    def delete(self, doc_id):
        """Delete a document. Return True if it exists."""
        count, _ = self._run(
            "DELETE FROM documents WHERE id = ?",
            (doc_id,)
        )
        return count > 0
