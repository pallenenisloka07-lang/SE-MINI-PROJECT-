
import os

from backend.app.database.connection import SessionLocal
from backend.app.database.security import hash_password
from backend.app.models.models import Category, User


DEFAULT_CATEGORIES = [
    ("Technology", "Technology, software, and computing documents"),
    ("Business and Finance", "Business, economics, and financial documents"),
    ("Education", "Educational and academic documents"),
    ("Health and Medicine", "Healthcare and medical documents"),
    ("Law and Government", "Legal and government documents"),
    ("Science and Research", "Scientific and research documents"),
]


def seed_categories(db):
    added = 0

    for name, description in DEFAULT_CATEGORIES:
        existing = db.query(Category).filter_by(name=name).first()

        if existing is None:
            db.add(Category(name=name, description=description))
            added += 1

    db.flush()
    print(f"Categories ready. Added {added}.")


def seed_admin(db):
    username = os.getenv("AI_CMS_ADMIN_USERNAME")
    email = os.getenv("AI_CMS_ADMIN_EMAIL")
    password = os.getenv("AI_CMS_ADMIN_PASSWORD")

    if not all([username, email, password]):
        print("Admin skipped: admin environment variables are not set.")
        return

    existing = db.query(User).filter_by(email=email).first()

    if existing:
        if existing.role != "admin":
            raise ValueError(
                "Configured admin email belongs to a non-admin user."
            )
        print("Admin already exists; no changes made.")
        return

    username_exists = db.query(User).filter_by(username=username).first()
    if username_exists:
        raise ValueError("Configured admin username is already in use.")

    admin = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="admin",
    )

    db.add(admin)
    db.flush()
    print("Admin account created.")


def seed_data():
    db = SessionLocal()

    try:
        seed_categories(db)
        seed_admin(db)
        db.commit()
        print("Seeding completed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()

