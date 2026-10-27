"""Isolated SQLite CRUD/FTS smoke checks (FR-007, FR-018 / TC-AI-09).

This test must never write to the configured development database.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.database import init_db
from backend.app.database.connection import Base
from backend.app.models.models import Document, User


def test_database_operations(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(init_db, "engine", engine)
    Session = sessionmaker(bind=engine)

    try:
        init_db.initialize_database()
        with Session.begin() as db:
            user = User(
                username="database_test_user",
                email="database_test@example.com",
                password_hash="test_hash",
                role="user",
            )
            db.add(user)
            db.flush()
            user_id = user.id
            document = Document(
                owner_id=user_id,
                title="First title",
                original_filename="sample.txt",
                file_type=".txt",
                file_size=16,
                storage_path="storage/test-only.txt",
                extracted_text="First searchable passage",
                status="Processed",
            )
            db.add(document)
            db.flush()
            document_id = document.id

        with Session.begin() as db:
            saved = db.get(User, user_id)
            assert saved is not None
            saved.username = "database_test_updated"
            saved_document = db.get(Document, document_id)
            assert saved_document is not None
            saved_document.title = "Updated searchable title"

        with Session() as db:
            assert db.get(User, user_id).username == "database_test_updated"
            matches = db.execute(
                text("SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'searchable'")
            ).scalars().all()
            assert matches == [document_id]

        with Session.begin() as db:
            db.delete(db.get(Document, document_id))
            db.delete(db.get(User, user_id))

        with Session() as db:
            assert db.get(User, user_id) is None
            assert db.get(Document, document_id) is None
            assert db.execute(
                text("SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'searchable'")
            ).scalars().all() == []
    finally:
        engine.dispose()
