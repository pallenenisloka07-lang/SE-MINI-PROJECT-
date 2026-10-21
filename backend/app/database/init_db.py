
from sqlalchemy import text

from backend.app.database.connection import Base, engine
from backend.app.models import models  # Registers all model classes


def initialize_database():
    """Create relational tables and keep the FTS5 search index synchronized."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(
                title,
                extracted_text,
                content='documents',
                content_rowid='id'
            )
        """))

        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS documents_ai
            AFTER INSERT ON documents
            BEGIN
                INSERT INTO documents_fts(rowid, title, extracted_text)
                VALUES (new.id, new.title, new.extracted_text);
            END
        """))

        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS documents_ad
            AFTER DELETE ON documents
            BEGIN
                INSERT INTO documents_fts(
                    documents_fts, rowid, title, extracted_text
                )
                VALUES (
                    'delete', old.id, old.title, old.extracted_text
                );
            END
        """))

        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS documents_au
            AFTER UPDATE OF title, extracted_text ON documents
            BEGIN
                INSERT INTO documents_fts(
                    documents_fts, rowid, title, extracted_text
                )
                VALUES (
                    'delete', old.id, old.title, old.extracted_text
                );

                INSERT INTO documents_fts(rowid, title, extracted_text)
                VALUES (new.id, new.title, new.extracted_text);
            END
        """))

        # Synchronize the index with existing document records.
        connection.execute(text("""
            INSERT INTO documents_fts(documents_fts) VALUES ('rebuild')
        """))

    print("AI-CMS database tables and synchronized FTS5 index initialized.")


if __name__ == "__main__":
    initialize_database()

