
import os
import bcrypt

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
    or_,
)

from src.repositories.user_repository import (
    Base,
    SessionLocal,
    engine,
    User,
)

from src.repositories.document_repository import Document


DEFAULT_CATEGORIES = {
    "Technology": (
        "Software, computers, programming, digital systems, "
        "artificial intelligence, data platforms and cybersecurity."
    ),
    "Business and Finance": (
        "Business strategy, companies, accounting, banking, "
        "investments, budgets, financial markets and commerce."
    ),
    "Education": (
        "Schools, universities, students, teaching, academic "
        "courses, learning methods, assessments and curriculum."
    ),
    "Health and Medicine": (
        "Healthcare, diseases, medical research, patients, "
        "clinical practice, diagnosis, treatment and medicine."
    ),
    "Law and Government": (
        "Legislation, courts, legal systems, public policy, "
        "government institutions, regulations and civic affairs."
    ),
    "Science and Research": (
        "Scientific methods, experiments, research findings, "
        "physics, chemistry, biology and academic investigations."
    ),
}


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    description = Column(String(500), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


class AuditEvent(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


def init_admin_tables():
    """Create admin tables and seed default categories and admin."""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Add any missing defaults without duplicating existing categories.
        existing_names = {
            category.name.strip().casefold()
            for category in db.query(Category).all()
        }

        for name, description in DEFAULT_CATEGORIES.items():
            if name.casefold() not in existing_names:
                db.add(
                    Category(
                        name=name,
                        description=description,
                    )
                )

        db.commit()

        # Administrator credentials are supplied through environment variables.
        username = os.getenv("AI_CMS_ADMIN_USERNAME")
        email = os.getenv("AI_CMS_ADMIN_EMAIL")
        password = os.getenv("AI_CMS_ADMIN_PASSWORD")

        credentials = (username, email, password)

        # Allow application startup without configured admin credentials.
        if not any(credentials):
            return

        if not all(credentials):
            raise RuntimeError(
                "Configure AI_CMS_ADMIN_USERNAME, "
                "AI_CMS_ADMIN_EMAIL and AI_CMS_ADMIN_PASSWORD."
            )

        username = username.strip()
        email = email.strip().lower()

        if not username or len(username) > 50:
            raise RuntimeError(
                "Administrator username must contain 1-50 characters."
            )

        if not email or len(email) > 254:
            raise RuntimeError(
                "Administrator email is invalid or too long."
            )

        # bcrypt processes at most 72 password bytes.
        if len(password.encode("utf-8")) > 72:
            raise RuntimeError(
                "Administrator password must not exceed 72 UTF-8 bytes."
            )

        existing_users = (
            db.query(User)
            .filter(
                or_(
                    func.lower(User.username) == username.lower(),
                    func.lower(User.email) == email,
                )
            )
            .all()
        )

        if existing_users:
            # Never silently promote an existing regular account.
            if (
                len(existing_users) == 1
                and existing_users[0].username == username
                and existing_users[0].email.lower() == email
                and str(existing_users[0].role).lower()
                in {"admin", "administrator"}
            ):
                return

            raise RuntimeError(
                "Administrator username or email conflicts with "
                "an existing account. Resolve the conflict explicitly."
            )

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        admin = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()


def list_categories():
    """Return all categories in alphabetical order."""
    with SessionLocal() as db:
        categories = (
            db.query(Category)
            .order_by(Category.name.asc())
            .all()
        )

        return [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
            }
            for item in categories
        ]


def create_category(name, description):
    """Create a category after validating its name and description."""
    if not isinstance(name, str) or not isinstance(description, str):
        raise ValueError(
            "Category name and description must be text."
        )

    name = name.strip()
    description = description.strip()

    if not name or len(name) > 100:
        raise ValueError(
            "Category name must contain 1-100 characters."
        )

    if name.casefold() == "uncategorized":
        raise ValueError(
            "Uncategorized is reserved for the system."
        )

    if not description or len(description) > 500:
        raise ValueError(
            "Description must contain 1-500 characters."
        )

    with SessionLocal() as db:
        existing = (
            db.query(Category)
            .filter(func.lower(Category.name) == name.lower())
            .first()
        )

        if existing:
            raise ValueError(
                "A category with this name already exists."
            )

        category = Category(
            name=name,
            description=description,
        )

        db.add(category)
        db.commit()
        db.refresh(category)

        return {
            "id": category.id,
            "name": category.name,
            "description": category.description,
        }


def delete_category(category_id):
    """Delete a category and reset associated documents."""
    with SessionLocal() as db:
        category = db.get(Category, category_id)

        if category is None:
            return None

        category_data = {
            "id": category.id,
            "name": category.name,
            "description": category.description,
        }

        documents = (
            db.query(Document)
            .filter(
                func.lower(Document.category)
                == category.name.lower()
            )
            .all()
        )

        affected_count = len(documents)

        for document in documents:
            document.category = "Uncategorized"
            document.category_confidence = None
            document.category_is_manual = False

        db.delete(category)
        db.commit()

        return {
            "category": category_data,
            "documents_reset": affected_count,
        }


def record_audit_event(
    user_id,
    username,
    action,
    details="",
):
    """Store an audit event without passwords, tokens or document text."""
    if not isinstance(action, str) or not action.strip():
        raise ValueError("Audit action is required.")

    with SessionLocal() as db:
        event = AuditEvent(
            user_id=user_id,
            username=(username or "")[:100] or None,
            action=action.strip()[:100],
            details=(details or "")[:1000],
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return {
            "id": event.id,
            "user_id": event.user_id,
            "username": event.username,
            "action": event.action,
            "details": event.details,
            "created_at": event.created_at,
        }


def list_audit_events(offset=0, limit=10):
    """Return newest audit events first with pagination."""
    if offset < 0 or limit < 1 or limit > 100:
        raise ValueError(
            "Offset must be non-negative and limit must be 1-100."
        )

    with SessionLocal() as db:
        query = db.query(AuditEvent)
        total = query.count()

        events = (
            query.order_by(
                AuditEvent.created_at.desc(),
                AuditEvent.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            {
                "id": event.id,
                "user_id": event.user_id,
                "username": event.username,
                "action": event.action,
                "details": event.details,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]

        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
        }
