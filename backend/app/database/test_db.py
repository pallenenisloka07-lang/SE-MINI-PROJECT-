
from backend.app.database.connection import SessionLocal
from backend.app.database.init_db import initialize_database
from backend.app.models.models import User


def test_database_operations():
    initialize_database()
    db = SessionLocal()
    test_email = "database_test@example.com"

    try:
        existing_user = db.query(User).filter_by(
            email=test_email
        ).first()

        if existing_user:
            db.delete(existing_user)
            db.commit()

        user = User(
            username="database_test_user",
            email=test_email,
            password_hash="test_hash",
            role="user",
        )

        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        print("CREATE: PASS")

        saved_user = db.query(User).filter_by(id=user_id).first()
        print("READ:", "PASS" if saved_user else "FAIL")

        saved_user.username = "database_test_updated"
        db.commit()
        db.refresh(saved_user)
        print(
            "UPDATE:",
            "PASS"
            if saved_user.username == "database_test_updated"
            else "FAIL",
        )

        db.delete(saved_user)
        db.commit()
        deleted_user = db.query(User).filter_by(id=user_id).first()
        print("DELETE:", "PASS" if deleted_user is None else "FAIL")

    finally:
        db.close()


if __name__ == "__main__":
    test_database_operations()

