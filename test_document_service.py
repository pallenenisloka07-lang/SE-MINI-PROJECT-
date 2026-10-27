
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.models import Base, User, Category, Document
from backend.app.services.document_service import (
    update_document,
    delete_document,
)
from backend.app.storage.file_storage import save_file, get_file


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def enable_test_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


Base.metadata.create_all(bind=engine)
TestingSession = sessionmaker(bind=engine)
db = TestingSession()

storage_path = None

try:
    user = User(
        username="test_user",
        email="test_user@example.com",
        password_hash="test_hash",
    )
    category1 = Category(
        name="Test General",
        description="Test category",
    )
    category2 = Category(
        name="Test Academic",
        description="Test category",
    )
    db.add_all([user, category1, category2])
    db.commit()

    content = b"Temporary test content"
    storage_path = save_file(content, "service_test.txt")

    document = Document(
        owner_id=user.id,
        category_id=category1.id,
        title="Original title",
        original_filename="service_test.txt",
        file_type="txt",
        file_size=len(content),
        storage_path=storage_path,
        extracted_text=content.decode(),
    )
    db.add(document)
    db.commit()

    document_id = document.id
    user_id = user.id
    category2_id = category2.id
    actual_file_path = get_file(storage_path)

    # Test title and category update.
    updated = update_document(
        db,
        document_id=document_id,
        owner_id=user_id,
        title="Updated title",
        category_id=category2_id,
    )

    assert updated is not None
    assert updated.title == "Updated title"
    assert updated.category_id == category2_id
    assert updated.category_source == "manual"
    print("UPDATE TITLE/CATEGORY: PASS")

    # Reject an empty title without changing the stored title.
    try:
        update_document(
            db,
            document_id=document_id,
            owner_id=user_id,
            title="   ",
        )
        raise AssertionError("Empty title should have been rejected.")
    except ValueError:
        db.rollback()

    assert db.query(Document).filter(
        Document.id == document_id
    ).first().title == "Updated title"
    print("EMPTY TITLE VALIDATION: PASS")

    # Reject a category ID that does not exist.
    try:
        update_document(
            db,
            document_id=document_id,
            owner_id=user_id,
            category_id=999999,
        )
        raise AssertionError("Missing category should have been rejected.")
    except ValueError:
        db.rollback()

    print("INVALID CATEGORY VALIDATION: PASS")

    # A different user must not be able to update the document.
    assert update_document(
        db,
        document_id=document_id,
        owner_id=999999,
        title="Unauthorized title",
    ) is None
    print("OWNER CHECK: PASS")

    # Delete the document and verify database and file cleanup.
    assert actual_file_path.is_file()

    assert delete_document(
        db,
        document_id=document_id,
        owner_id=user_id,
    ) is True

    assert db.query(Document).filter(
        Document.id == document_id
    ).first() is None
    assert not actual_file_path.exists()
    print("DELETE DATABASE RECORD AND REAL FILE: PASS")

    # Repeated deletion should report that the document is missing.
    assert delete_document(
        db,
        document_id=document_id,
        owner_id=user_id,
    ) is False
    print("MISSING DOCUMENT CHECK: PASS")

finally:
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

    # Clean up the real test file if a test fails before deletion.
    if storage_path:
        try:
            get_file(storage_path).unlink()
        except FileNotFoundError:
            pass